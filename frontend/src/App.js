import React from 'react';
import { BrowserRouter, Routes, Route, Outlet } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Layout from './components/layout/Layout';
import { ProtectedRoute, AdminRoute } from './components/common/ProtectedRoute';

// Pages
import HomePage          from './pages/HomePage';
import ShopPage          from './pages/ShopPage';
import ProductDetailPage from './pages/ProductDetailPage';
import CartPage          from './pages/CartPage';
import CheckoutPage      from './pages/CheckoutPage';
import LoginPage         from './pages/LoginPage';
import RegisterPage      from './pages/RegisterPage';
import OAuthCallbackPage from './pages/OAuthCallbackPage';
import OrdersPage        from './pages/OrdersPage';
import ProfilePage       from './pages/ProfilePage';
import AdminPage         from './pages/AdminPage';
import WishlistPage      from './pages/WishlistPage';

// ── Layout wrapper that renders <Outlet> inside ───────────────────────────────
function LayoutWrapper() {
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}

// ── 404 ───────────────────────────────────────────────────────────────────────
function NotFoundPage() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4 animate-fade-in">
      <p className="text-9xl font-display font-extrabold gradient-text mb-4">404</p>
      <h1 className="text-2xl font-bold text-gray-800 mb-2">Page Not Found</h1>
      <p className="text-gray-500 mb-8 max-w-sm">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <a href="/" className="btn-primary px-8 py-3">← Back to Home</a>
    </div>
  );
}

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Auth pages — standalone (no Navbar/Footer) */}
          <Route path="/login"          element={<LoginPage />} />
          <Route path="/register"       element={<RegisterPage />} />
          <Route path="/oauth/callback" element={<OAuthCallbackPage />} />

          {/* All other pages — wrapped in Layout */}
          <Route element={<LayoutWrapper />}>
            <Route path="/"              element={<HomePage />} />
            <Route path="/shop"          element={<ShopPage />} />
            <Route path="/product/:slug" element={<ProductDetailPage />} />
            <Route path="/cart"          element={<CartPage />} />

            {/* Protected: must be logged in */}
            <Route path="/checkout" element={
              <ProtectedRoute><CheckoutPage /></ProtectedRoute>
            } />
            <Route path="/orders" element={
              <ProtectedRoute><OrdersPage /></ProtectedRoute>
            } />
            <Route path="/profile" element={
              <ProtectedRoute><ProfilePage /></ProtectedRoute>
            } />
            <Route path="/wishlist" element={
              <ProtectedRoute><WishlistPage /></ProtectedRoute>
            } />

            {/* Admin only */}
            <Route path="/admin" element={
              <AdminRoute><AdminPage /></AdminRoute>
            } />

            {/* Catch-all 404 */}
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
