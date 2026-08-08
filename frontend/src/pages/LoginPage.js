import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { FiMail, FiLock, FiEye, FiEyeOff, FiArrowRight } from 'react-icons/fi';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL } from '../api/client';
import useCartStore from '../store/cartStore';
import GoogleIcon from '../components/common/GoogleIcon';
import toast from 'react-hot-toast';

export default function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const fetchCart = useCartStore((s) => s.fetchCart);
  const mergeGuestCart = useCartStore((s) => s.mergeGuestCart);
  const guestItems = useCartStore((s) => s.items);
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  const [form, setForm] = useState({ email: '', password: '' });
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);

  // Already logged in — redirect
  React.useEffect(() => {
    if (isAuthenticated) navigate(from, { replace: true });
  }, [isAuthenticated, navigate, from]);

  const handleChange = (e) => setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.email || !form.password) { toast.error('Please fill in all fields'); return; }
    setLoading(true);
    try {
      await login(form.email, form.password);
      // Merge any guest cart items then fetch server cart
      if (guestItems.length > 0) {
        await mergeGuestCart(guestItems);
      } else {
        await fetchCart();
      }
      navigate(from, { replace: true });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  // Demo credentials helper
  const fillDemo = (role) => {
    if (role === 'admin') setForm({ email: 'admin@shop.com', password: 'admin123' });
    else setForm({ email: 'demo@shop.com', password: 'demo123' });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-accent-50 flex items-center justify-center px-4 py-16">
      <div className="w-full max-w-md animate-slide-up">
        {/* Card */}
        <div className="bg-white rounded-3xl shadow-card-hover p-8 sm:p-10">
          {/* Header */}
          <div className="text-center mb-8">
            <Link to="/" className="text-3xl font-display font-bold gradient-text inline-block mb-4">
              ShopVibe
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">Welcome back</h1>
            <p className="text-gray-500 text-sm mt-1">Sign in to your account to continue</p>
          </div>

          {/* Demo credentials */}
          <div className="flex gap-2 mb-6">
            <button onClick={() => fillDemo('admin')}
              className="flex-1 text-xs py-2 rounded-xl bg-primary-50 text-primary-700 font-semibold hover:bg-primary-100 transition-colors border border-primary-100">
              🔑 Demo Admin
            </button>
            <button onClick={() => fillDemo('user')}
              className="flex-1 text-xs py-2 rounded-xl bg-gray-50 text-gray-600 font-semibold hover:bg-gray-100 transition-colors border border-gray-100">
              👤 Demo User
            </button>
          </div>

          {new URLSearchParams(location.search).get('error') && (
            <p className="mb-4 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
              Google sign-in failed. Please try again or use your password.
            </p>
          )}

          {/* Google OAuth */}
          <a
            href={`${BACKEND_URL}/api/auth/google/login`}
            className="w-full flex items-center justify-center gap-2.5 py-3 rounded-xl border border-gray-200 text-gray-700 font-semibold hover:bg-gray-50 transition-colors mb-4"
          >
            <GoogleIcon />
            Continue with Google
          </a>

          <div className="flex items-center gap-3 mb-4">
            <span className="flex-1 h-px bg-gray-200" />
            <span className="text-xs text-gray-400 font-medium">or sign in with email</span>
            <span className="flex-1 h-px bg-gray-200" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1.5">Email Address</label>
              <div className="relative">
                <FiMail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input name="email" type="email" value={form.email} onChange={handleChange}
                  placeholder="you@example.com" autoComplete="email"
                  className="input pl-10" required />
              </div>
            </div>

            {/* Password */}
            <div>
              <div className="flex justify-between mb-1.5">
                <label className="text-xs font-semibold text-gray-600">Password</label>
                <button type="button" className="text-xs text-primary-600 hover:text-primary-700 font-medium">
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <FiLock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input name="password" type={showPw ? 'text' : 'password'} value={form.password}
                  onChange={handleChange} placeholder="••••••••" autoComplete="current-password"
                  className="input pl-10 pr-10" required />
                <button type="button" onClick={() => setShowPw((s) => !s)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  {showPw ? <FiEyeOff size={16} /> : <FiEye size={16} />}
                </button>
              </div>
            </div>

            <button type="submit" disabled={loading}
              className="btn-primary w-full py-3 text-base gap-2 mt-2">
              {loading ? 'Signing in…' : <>Sign In <FiArrowRight size={18} /></>}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Don't have an account?{' '}
            <Link to="/register" className="text-primary-600 font-semibold hover:text-primary-700 transition-colors">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
