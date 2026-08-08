from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import List, Optional
from datetime import datetime


# ── Auth ──────────────────────────────────────────────────────────────────────
class UserRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    avatar_url: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


# ── Category ──────────────────────────────────────────────────────────────────
class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None
    image_url: Optional[str] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    image_url: Optional[str]

    class Config:
        from_attributes = True


# ── Product ───────────────────────────────────────────────────────────────────
class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=220, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None
    price: float = Field(gt=0, description="Must be > 0")
    original_price: Optional[float] = Field(None, gt=0)
    image_url: Optional[str] = None
    images: Optional[str] = None
    category_id: Optional[int] = None
    stock_quantity: int = Field(0, ge=0, description="Cannot be negative")
    is_featured: bool = False
    brand: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = None

    @model_validator(mode="after")
    def original_price_gte_price(self) -> "ProductCreate":
        if self.original_price and self.original_price <= self.price:
            raise ValueError("original_price must be greater than price")
        return self


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    original_price: Optional[float] = Field(None, gt=0)
    image_url: Optional[str] = None
    images: Optional[str] = None
    category_id: Optional[int] = None
    stock_quantity: Optional[int] = Field(None, ge=0)
    is_featured: Optional[bool] = None
    is_active: Optional[bool] = None
    brand: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = None


class ProductOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    price: float
    original_price: Optional[float]
    image_url: Optional[str]
    images: Optional[str]
    category: Optional[CategoryOut]
    stock_quantity: int
    is_featured: bool
    is_active: bool
    rating: float
    review_count: int
    brand: Optional[str]
    tags: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Cart ──────────────────────────────────────────────────────────────────────
class CartItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(1, ge=1, le=100)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=100)


class CartItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    product: ProductOut

    class Config:
        from_attributes = True


# ── Orders ────────────────────────────────────────────────────────────────────
class OrderItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: float
    product: ProductOut

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    shipping_address: str = Field(min_length=10, max_length=500)
    payment_method: str = Field("card", pattern=r"^(card|paypal|cod|stripe)$")
    notes: Optional[str] = Field(None, max_length=500)


class OrderOut(BaseModel):
    id: int
    status: str
    total_amount: float
    shipping_address: str
    payment_method: str
    payment_status: str
    stripe_session_id: Optional[str]
    notes: Optional[str]
    is_fraud_flagged: bool = False
    fraud_reason: Optional[str] = None
    created_at: datetime
    items: List[OrderItemOut]

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(pending|processing|shipped|delivered|cancelled)$")


# ── Review ────────────────────────────────────────────────────────────────────
class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    comment: Optional[str] = Field(None, max_length=2000)


class ReviewOut(BaseModel):
    id: int
    rating: int
    title: Optional[str]
    comment: Optional[str]
    created_at: datetime
    user: UserOut

    class Config:
        from_attributes = True


# ── Pagination ────────────────────────────────────────────────────────────────
class ProductsResponse(BaseModel):
    items: List[ProductOut]
    total: int
    page: int
    pages: int


# ── Wishlist ──────────────────────────────────────────────────────────────────
class WishlistItemOut(BaseModel):
    id: int
    product_id: int
    product: ProductOut
    created_at: datetime

    class Config:
        from_attributes = True


# ── Search ────────────────────────────────────────────────────────────────────
class SearchSuggestion(BaseModel):
    id: int
    name: str
    slug: str
    price: float
    image_url: Optional[str]
    category: Optional[str]


# ── Stripe ────────────────────────────────────────────────────────────────────
class StripeSessionOut(BaseModel):
    session_id: str
    url: str


class AdminStats(BaseModel):
    total_orders: int
    total_revenue: float
    total_products: int
    total_users: int


# ── Support tickets ───────────────────────────────────────────────────────────
class SupportTicketCreate(BaseModel):
    subject: str = Field(min_length=2, max_length=200)
    message: str = Field(min_length=2, max_length=5000)
    order_id: Optional[int] = Field(None, gt=0)


class SupportTicketOut(BaseModel):
    id: int
    user_id: int
    order_id: Optional[int]
    subject: str
    message: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TicketStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(open|resolved)$")


# ── Agentic AI ────────────────────────────────────────────────────────────────
class AIAgentRequest(BaseModel):
    instruction: str = Field(min_length=2, max_length=2000)


class AIAgentResponse(BaseModel):
    reply: str
    actions: List[dict]
