import stripe
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, func, text as _sql
from sqlalchemy.orm import Session
from typing import List, Optional
from database import engine, get_db, Base
import models
import schemas
import google_oauth
from auth import hash_password, verify_password, create_access_token, get_current_user, get_current_admin
from ai_agent import run_agent
from config import settings
from logger import setup_logging, RequestLoggingMiddleware, logger
from monitoring import MetricsMiddleware, metrics_response
from seed import seed as run_seed
from integrations import salesforce

setup_logging("INFO" if settings.app_env == "production" else "DEBUG")
stripe.api_key = settings.stripe_secret_key

# ── Startup ───────────────────────────────────────────────────────────────────


def _init_db() -> None:
    """Create tables + enum types. Skips Postgres-specific DDL when using SQLite (tests)."""
    is_postgres = "postgresql" in settings.database_url or "postgres" in settings.database_url
    if is_postgres:
        _CREATE_ENUMS = """
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
        CREATE TYPE userrole AS ENUM ('customer', 'admin');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'orderstatus') THEN
        CREATE TYPE orderstatus AS ENUM ('pending', 'processing', 'shipped', 'delivered', 'cancelled');
    END IF;
END $$;
"""
        with engine.connect() as _conn:
            _conn.execute(_sql(_CREATE_ENUMS))
            _conn.commit()
    Base.metadata.create_all(bind=engine)
    _migrate(engine)
    try:
        run_seed()
    except Exception as exc:
        logger.info("Seed skipped: %s", exc)


def _migrate(db_engine) -> None:
    """Idempotent column migrations for databases created before new columns existed."""
    is_postgres = "postgresql" in settings.database_url or "postgres" in settings.database_url
    if not is_postgres:
        return
    statements = [
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS salesforce_id VARCHAR(18)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS sf_contact_id VARCHAR(18)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS sf_account_id VARCHAR(18)",
    ]
    with db_engine.connect() as _conn:
        for stmt in statements:
            _conn.execute(_sql(stmt))
        _conn.commit()


@asynccontextmanager
async def lifespan(app_instance):  # noqa: F841
    # DB init + seeding only in prod/dev — never during tests (test env
    # creates its own schema via conftest, seeding would pollute it)
    if settings.app_env != "test" and (
        "postgresql" in settings.database_url or "postgres" in settings.database_url
    ):
        _init_db()
    yield

app = FastAPI(
    title="ShopVibe API", version="3.0.0",
    description="Full-stack e-commerce REST API — FastAPI + PostgreSQL (OAuth, Salesforce, AI, monitoring)",
    docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.origins_list,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["Health"])
def health():
    return {"status": "ok", "env": settings.app_env}

# ── Monitoring ─────────────────────────────────────────────────────────────────
@app.get("/metrics", include_in_schema=False)
def metrics():
    return metrics_response()

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.post("/api/auth/register", response_model=schemas.Token, status_code=201, tags=["Auth"])
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(400, "Email already registered")
    user = models.User(name=payload.name, email=payload.email,
                       hashed_password=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    logger.info("New user registered: %s", user.email)
    return {"access_token": token, "token_type": "bearer", "user": user}

@app.post("/api/auth/login", response_model=schemas.Token, tags=["Auth"])
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account deactivated")
    return {"access_token": create_access_token({"sub": str(user.id)}),
            "token_type": "bearer", "user": user}

@app.get("/api/auth/me", response_model=schemas.UserOut, tags=["Auth"])
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.put("/api/auth/me", response_model=schemas.UserOut, tags=["Auth"])
def update_me(payload: schemas.UserUpdate, db: Session = Depends(get_db),
              current_user: models.User = Depends(get_current_user)):
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(current_user, k, v)
    db.commit(); db.refresh(current_user)
    return current_user

@app.put("/api/auth/me/password", tags=["Auth"])
def change_password(payload: schemas.PasswordChange, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password changed successfully"}

# ── Google OAuth ──────────────────────────────────────────────────────────────
@app.get("/api/auth/google/login", tags=["Auth"])
def google_login():
    if not google_oauth.google_configured():
        raise HTTPException(503, "Google OAuth is not configured (set GOOGLE_CLIENT_ID/SECRET)")
    state = google_oauth.make_state()
    return RedirectResponse(google_oauth.authorization_url(state), status_code=302)

@app.get("/api/auth/google/callback", tags=["Auth"])
def google_callback(code: str, state: str = "", db: Session = Depends(get_db)):
    if not google_oauth.verify_state(state):
        logger.warning("Google OAuth callback rejected: invalid state")
        return RedirectResponse(f"{settings.frontend_url}/login?error=invalid_state", status_code=302)
    try:
        tokens = google_oauth.exchange_code(code)
        info = google_oauth.verify_id_token(tokens["id_token"])
    except Exception as exc:  # noqa: BLE001 - any OAuth failure just redirects back
        logger.warning("Google OAuth callback failed: %s", exc)
        return RedirectResponse(f"{settings.frontend_url}/login?error=google_login_failed", status_code=302)
    email = info["email"].lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        user = models.User(
            name=info.get("name") or email.split("@")[0],
            email=email,
            hashed_password=hash_password(google_oauth.google_user_password()),
        )
        db.add(user); db.commit(); db.refresh(user)
        logger.info("New user created via Google: %s", email)
    elif not user.is_active:
        return RedirectResponse(f"{settings.frontend_url}/login?error=account_deactivated", status_code=302)
    token = create_access_token({"sub": str(user.id)})
    return RedirectResponse(f"{settings.frontend_url}/oauth/callback?token={token}", status_code=302)

# ── Categories ──────────────────────────────────────────────────────────────────
@app.get("/api/categories", response_model=List[schemas.CategoryOut], tags=["Categories"])
def list_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).all()

@app.post("/api/categories", response_model=schemas.CategoryOut, status_code=201, tags=["Categories"])
def create_category(payload: schemas.CategoryCreate, db: Session = Depends(get_db),
                    _: models.User = Depends(get_current_admin)):
    if db.query(models.Category).filter(models.Category.slug == payload.slug).first():
        raise HTTPException(400, "Slug already exists")
    cat = models.Category(**payload.model_dump())
    db.add(cat); db.commit(); db.refresh(cat)
    return cat

# ── Products ────────────────────────────────────────────────────────────────────
@app.get("/api/products", response_model=schemas.ProductsResponse, tags=["Products"])
def list_products(
    page: int = Query(1, ge=1), per_page: int = Query(12, ge=1, le=100),
    q: Optional[str] = None, category: Optional[str] = None,
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    sort: Optional[str] = Query("newest", pattern=r"^(newest|price_asc|price_desc|rating|name)$"),
    featured: Optional[bool] = None, db: Session = Depends(get_db),
):
    qry = db.query(models.Product).filter(models.Product.is_active == True)  # noqa: E712
    if q:
        qry = qry.filter(or_(models.Product.name.ilike(f"%{q}%"),
                              models.Product.description.ilike(f"%{q}%"),
                              models.Product.brand.ilike(f"%{q}%")))
    if category:
        qry = qry.join(models.Category).filter(models.Category.slug == category)
    if min_price is not None: qry = qry.filter(models.Product.price >= min_price)
    if max_price is not None: qry = qry.filter(models.Product.price <= max_price)
    if featured is not None: qry = qry.filter(models.Product.is_featured == featured)
    sort_map = {"newest": models.Product.created_at.desc(), "price_asc": models.Product.price.asc(),
                "price_desc": models.Product.price.desc(), "rating": models.Product.rating.desc(),
                "name": models.Product.name.asc()}
    qry = qry.order_by(sort_map[sort])
    total = qry.count()
    items = qry.offset((page - 1) * per_page).limit(per_page).all()
    return {"items": items, "total": total, "page": page, "pages": -(-total // per_page)}

@app.get("/api/products/{slug}", response_model=schemas.ProductOut, tags=["Products"])
def get_product(slug: str, db: Session = Depends(get_db)):
    p = db.query(models.Product).filter(models.Product.slug == slug, models.Product.is_active == True).first()  # noqa: E712
    if not p: raise HTTPException(404, "Product not found")
    return p

@app.post("/api/products", response_model=schemas.ProductOut, status_code=201, tags=["Products"])
def create_product(payload: schemas.ProductCreate, db: Session = Depends(get_db),
                   _: models.User = Depends(get_current_admin)):
    if db.query(models.Product).filter(models.Product.slug == payload.slug).first():
        raise HTTPException(400, "Slug already exists")
    p = models.Product(**payload.model_dump())
    db.add(p); db.commit(); db.refresh(p)
    return p

@app.put("/api/products/{product_id}", response_model=schemas.ProductOut, tags=["Products"])
def update_product(product_id: int, payload: schemas.ProductUpdate,
                   db: Session = Depends(get_db), _: models.User = Depends(get_current_admin)):
    p = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not p: raise HTTPException(404, "Product not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    db.commit(); db.refresh(p)
    return p

@app.delete("/api/products/{product_id}", status_code=204, tags=["Products"])
def delete_product(product_id: int, db: Session = Depends(get_db),
                   _: models.User = Depends(get_current_admin)):
    p = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not p: raise HTTPException(404, "Product not found")
    db.delete(p); db.commit()

# ── Reviews ──────────────────────────────────────────────────────────────────────
@app.get("/api/products/{product_id}/reviews", response_model=List[schemas.ReviewOut], tags=["Reviews"])
def list_reviews(product_id: int, db: Session = Depends(get_db)):
    return db.query(models.Review).filter(models.Review.product_id == product_id).all()

@app.post("/api/products/{product_id}/reviews", response_model=schemas.ReviewOut, status_code=201, tags=["Reviews"])
def create_review(product_id: int, payload: schemas.ReviewCreate, db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    p = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not p: raise HTTPException(404, "Product not found")
    r = models.Review(user_id=current_user.id, product_id=product_id, **payload.model_dump())
    db.add(r); db.flush()
    avg = db.query(func.avg(models.Review.rating)).filter(models.Review.product_id == product_id).scalar()
    cnt = db.query(func.count(models.Review.id)).filter(models.Review.product_id == product_id).scalar()
    p.rating = round(float(avg), 1); p.review_count = cnt
    db.commit(); db.refresh(r)
    return r

# ── Cart ─────────────────────────────────────────────────────────────────────────
@app.get("/api/cart", response_model=List[schemas.CartItemOut], tags=["Cart"])
def get_cart(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).all()

@app.post("/api/cart", response_model=schemas.CartItemOut, status_code=201, tags=["Cart"])
def add_to_cart(payload: schemas.CartItemCreate, db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    product = db.query(models.Product).filter(models.Product.id == payload.product_id,
                                               models.Product.is_active == True).first()  # noqa: E712
    if not product: raise HTTPException(404, "Product not found")
    if product.stock_quantity < payload.quantity:
        raise HTTPException(400, f"Only {product.stock_quantity} units in stock")
    existing = db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id,
                                                 models.CartItem.product_id == payload.product_id).first()
    if existing:
        existing.quantity += payload.quantity; db.commit(); db.refresh(existing); return existing
    item = models.CartItem(user_id=current_user.id, **payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item

@app.put("/api/cart/{item_id}", response_model=schemas.CartItemOut, tags=["Cart"])
def update_cart(item_id: int, payload: schemas.CartItemUpdate, db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    item = db.query(models.CartItem).filter(models.CartItem.id == item_id,
                                             models.CartItem.user_id == current_user.id).first()
    if not item: raise HTTPException(404, "Cart item not found")
    item.quantity = payload.quantity; db.commit(); db.refresh(item)
    return item

@app.delete("/api/cart/{item_id}", status_code=204, tags=["Cart"])
def remove_from_cart(item_id: int, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    item = db.query(models.CartItem).filter(models.CartItem.id == item_id,
                                             models.CartItem.user_id == current_user.id).first()
    if not item: raise HTTPException(404, "Cart item not found")
    db.delete(item); db.commit()

@app.delete("/api/cart", status_code=204, tags=["Cart"])
def clear_cart(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).delete()
    db.commit()

# ── Orders ───────────────────────────────────────────────────────────────────────
@app.post("/api/orders", response_model=schemas.OrderOut, status_code=201, tags=["Orders"])
def create_order(payload: schemas.OrderCreate, db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    cart = db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).all()
    if not cart: raise HTTPException(400, "Cart is empty")
    total = sum(i.product.price * i.quantity for i in cart)
    order = models.Order(user_id=current_user.id, total_amount=total, **payload.model_dump())
    db.add(order); db.flush()
    for item in cart:
        db.add(models.OrderItem(order_id=order.id, product_id=item.product_id,
                                quantity=item.quantity, unit_price=item.product.price))
        item.product.stock_quantity = max(0, item.product.stock_quantity - item.quantity)
    db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).delete()
    db.commit(); db.refresh(order)
    logger.info("Order #%d created by user %d — $%.2f", order.id, current_user.id, total)
    salesforce.sync_order(order, db)
    return order

@app.get("/api/orders", response_model=List[schemas.OrderOut], tags=["Orders"])
def list_my_orders(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Order).filter(models.Order.user_id == current_user.id)\
             .order_by(models.Order.created_at.desc()).all()

@app.get("/api/orders/{order_id}", response_model=schemas.OrderOut, tags=["Orders"])
def get_order(order_id: int, db: Session = Depends(get_db),
              current_user: models.User = Depends(get_current_user)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order or (order.user_id != current_user.id and current_user.role != models.UserRole.admin):
        raise HTTPException(404, "Order not found")
    return order

# ── Stripe ───────────────────────────────────────────────────────────────────────
@app.post("/api/payments/create-session", response_model=schemas.StripeSessionOut, tags=["Payments"])
def create_stripe_session(order_id: int, db: Session = Depends(get_db),
                          current_user: models.User = Depends(get_current_user)):
    order = db.query(models.Order).filter(models.Order.id == order_id,
                                           models.Order.user_id == current_user.id).first()
    if not order: raise HTTPException(404, "Order not found")
    if order.payment_status == "paid": raise HTTPException(400, "Already paid")
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": item.product.name,
                                     "images": [item.product.image_url] if item.product.image_url else []},
                    "unit_amount": int(item.unit_price * 100),
                }, "quantity": item.quantity,
            } for item in order.items],
            mode="payment",
            success_url="http://localhost/orders?paid=true",
            cancel_url="http://localhost/orders",
            metadata={"order_id": str(order.id)},
        )
        order.stripe_session_id = session.id; db.commit()
        return {"session_id": session.id, "url": session.url}
    except stripe.error.StripeError as e:
        logger.error("Stripe error: %s", e)
        raise HTTPException(502, "Payment service unavailable")

@app.post("/api/payments/webhook", tags=["Payments"])
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, "Invalid webhook signature")
    if event["type"] == "checkout.session.completed":
        session_obj = event["data"]["object"]
        order = db.query(models.Order).filter(
            models.Order.id == int(session_obj["metadata"].get("order_id", 0))).first()
        if order:
            order.payment_status = "paid"; order.status = models.OrderStatus.processing
            db.commit()
            logger.info("Payment confirmed for order #%d", order.id)
            salesforce.sync_order(order, db)
    return {"received": True}

# ── Wishlist ────────────────────────────────────────────────────────────────────
@app.get("/api/wishlist", response_model=List[schemas.WishlistItemOut], tags=["Wishlist"])
def get_wishlist(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.WishlistItem).filter(models.WishlistItem.user_id == current_user.id)\
             .order_by(models.WishlistItem.created_at.desc()).all()

@app.post("/api/wishlist/{product_id}", status_code=201, tags=["Wishlist"])
def add_to_wishlist(product_id: int, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    if not db.query(models.Product).filter(models.Product.id == product_id).first():
        raise HTTPException(404, "Product not found")
    if db.query(models.WishlistItem).filter(models.WishlistItem.user_id == current_user.id,
                                             models.WishlistItem.product_id == product_id).first():
        return {"message": "Already in wishlist"}
    item = models.WishlistItem(user_id=current_user.id, product_id=product_id)
    db.add(item); db.commit(); db.refresh(item)
    return {"message": "Added to wishlist", "id": item.id}

@app.delete("/api/wishlist/{product_id}", status_code=204, tags=["Wishlist"])
def remove_from_wishlist(product_id: int, db: Session = Depends(get_db),
                         current_user: models.User = Depends(get_current_user)):
    item = db.query(models.WishlistItem).filter(models.WishlistItem.user_id == current_user.id,
                                                 models.WishlistItem.product_id == product_id).first()
    if not item: raise HTTPException(404, "Not in wishlist")
    db.delete(item); db.commit()

@app.get("/api/wishlist/check/{product_id}", tags=["Wishlist"])
def check_wishlist(product_id: int, db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    exists = db.query(models.WishlistItem).filter(models.WishlistItem.user_id == current_user.id,
                                                   models.WishlistItem.product_id == product_id).first()
    return {"wishlisted": exists is not None}

# ── Search & Related ────────────────────────────────────────────────────────────
@app.get("/api/search/suggestions", response_model=List[schemas.SearchSuggestion], tags=["Search"])
def search_suggestions(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    results = db.query(models.Product).filter(
        models.Product.is_active == True,  # noqa: E712
        or_(models.Product.name.ilike(f"%{q}%"), models.Product.brand.ilike(f"%{q}%"),
            models.Product.tags.ilike(f"%{q}%"))).limit(8).all()
    return [{"id": p.id, "name": p.name, "slug": p.slug, "price": p.price,
             "image_url": p.image_url, "category": p.category.name if p.category else None}
            for p in results]

@app.get("/api/products/{product_id}/related", response_model=List[schemas.ProductOut], tags=["Products"])
def get_related(product_id: int, limit: int = Query(4, ge=1, le=12), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product: raise HTTPException(404, "Product not found")
    tag_list = [t.strip() for t in (product.tags or "").split(",") if t.strip()]
    scored = [(len(set(tag_list) & set([t.strip() for t in (p.tags or "").split(",") if t.strip()])), p)
              for p in db.query(models.Product).filter(models.Product.id != product_id,
                                                        models.Product.is_active == True).all()  # noqa: E712
              if set(tag_list) & set([t.strip() for t in (p.tags or "").split(",") if t.strip()])]
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [p for _, p in scored[:limit]]
    if len(top) < limit and product.category_id:
        eids = {p.id for p in top} | {product_id}
        top.extend(db.query(models.Product).filter(models.Product.category_id == product.category_id,
                                                    models.Product.id.notin_(eids),
                                                    models.Product.is_active == True  # noqa: E712
                                                    ).limit(limit - len(top)).all())
    return top[:limit]

# ── Admin ───────────────────────────────────────────────────────────────────────
@app.get("/api/admin/orders", response_model=List[schemas.OrderOut], tags=["Admin"])
def admin_list_orders(db: Session = Depends(get_db), _: models.User = Depends(get_current_admin)):
    return db.query(models.Order).order_by(models.Order.created_at.desc()).all()

@app.put("/api/admin/orders/{order_id}/status", response_model=schemas.OrderOut, tags=["Admin"])
def admin_update_order(order_id: int, payload: schemas.OrderStatusUpdate,
                       db: Session = Depends(get_db), _: models.User = Depends(get_current_admin)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order: raise HTTPException(404, "Order not found")
    order.status = payload.status; db.commit(); db.refresh(order)
    salesforce.sync_order(order, db)
    return order

@app.get("/api/admin/stats", response_model=schemas.AdminStats, tags=["Admin"])
def admin_stats(db: Session = Depends(get_db), _: models.User = Depends(get_current_admin)):
    return {
        "total_orders": db.query(models.Order).count(),
        "total_revenue": round(db.query(func.sum(models.Order.total_amount)).scalar() or 0, 2),
        "total_products": db.query(models.Product).count(),
        "total_users": db.query(models.User).count(),
    }

@app.post("/api/admin/orders/{order_id}/sync-salesforce", tags=["Admin"])
def admin_sync_order_to_salesforce(order_id: int, db: Session = Depends(get_db),
                                   _: models.User = Depends(get_current_admin)):
    if not salesforce.sf_configured():
        raise HTTPException(503, "Salesforce is not configured (set SF_* env vars)")
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order: raise HTTPException(404, "Order not found")
    if salesforce.sync_order(order, db):
        return {"message": f"Order #{order.id} synced to Salesforce"}
    raise HTTPException(502, "Salesforce sync failed — see server logs")

# ── Support tickets ────────────────────────────────────────────────────────────
@app.post("/api/tickets", response_model=schemas.SupportTicketOut, status_code=201, tags=["Tickets"])
def create_ticket(payload: schemas.SupportTicketCreate, db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    if payload.order_id:
        order = db.query(models.Order).filter(models.Order.id == payload.order_id).first()
        if not order or order.user_id != current_user.id:
            raise HTTPException(404, "Order not found")
    ticket = models.SupportTicket(user_id=current_user.id, **payload.model_dump())
    db.add(ticket); db.commit(); db.refresh(ticket)
    logger.info("Ticket #%d created by user %d", ticket.id, current_user.id)
    return ticket

@app.get("/api/tickets", response_model=List[schemas.SupportTicketOut], tags=["Tickets"])
def list_my_tickets(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    qry = db.query(models.SupportTicket)
    if current_user.role != models.UserRole.admin:
        qry = qry.filter(models.SupportTicket.user_id == current_user.id)
    return qry.order_by(models.SupportTicket.created_at.desc()).all()

@app.put("/api/tickets/{ticket_id}", response_model=schemas.SupportTicketOut, tags=["Tickets"])
def update_ticket(ticket_id: int, payload: schemas.TicketStatusUpdate,
                  db: Session = Depends(get_db), _: models.User = Depends(get_current_admin)):
    ticket = db.query(models.SupportTicket).filter(models.SupportTicket.id == ticket_id).first()
    if not ticket: raise HTTPException(404, "Ticket not found")
    ticket.status = payload.status
    db.commit(); db.refresh(ticket)
    return ticket

# ── Agentic AI ──────────────────────────────────────────────────────────────────
@app.post("/api/ai/agent", response_model=schemas.AIAgentResponse, tags=["AI"])
def ai_agent(payload: schemas.AIAgentRequest, db: Session = Depends(get_db),
             _: models.User = Depends(get_current_admin)):
    result = run_agent(db, payload.instruction)
    logger.info("AI agent ran: %d actions for %r", len(result["actions"]), payload.instruction)
    return result
