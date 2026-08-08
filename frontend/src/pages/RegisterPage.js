import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiUser, FiMail, FiLock, FiEye, FiEyeOff, FiArrowRight, FiCheck } from 'react-icons/fi';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL } from '../api/client';
import useCartStore from '../store/cartStore';
import GoogleIcon from '../components/common/GoogleIcon';
import toast from 'react-hot-toast';
import clsx from 'clsx';

const PASSWORD_RULES = [
  { label: 'At least 6 characters', test: (pw) => pw.length >= 6 },
  { label: 'One uppercase letter',  test: (pw) => /[A-Z]/.test(pw) },
  { label: 'One number',            test: (pw) => /\d/.test(pw) },
];

export default function RegisterPage() {
  const { register, isAuthenticated } = useAuth();
  const fetchCart = useCartStore((s) => s.fetchCart);
  const navigate = useNavigate();

  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' });
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);

  React.useEffect(() => {
    if (isAuthenticated) navigate('/', { replace: true });
  }, [isAuthenticated, navigate]);

  const handleChange = (e) => setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error('Please enter your name'); return; }
    if (form.password !== form.confirm) { toast.error('Passwords do not match'); return; }
    if (form.password.length < 6) { toast.error('Password must be at least 6 characters'); return; }
    setLoading(true);
    try {
      await register(form.name.trim(), form.email, form.password);
      await fetchCart();
      navigate('/', { replace: true });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 via-white to-accent-50 flex items-center justify-center px-4 py-16">
      <div className="w-full max-w-md animate-slide-up">
        <div className="bg-white rounded-3xl shadow-card-hover p-8 sm:p-10">
          {/* Header */}
          <div className="text-center mb-8">
            <Link to="/" className="text-3xl font-display font-bold gradient-text inline-block mb-4">
              ShopVibe
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">Create your account</h1>
            <p className="text-gray-500 text-sm mt-1">Join thousands of happy shoppers</p>
          </div>

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
            <span className="text-xs text-gray-400 font-medium">or sign up with email</span>
            <span className="flex-1 h-px bg-gray-200" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1.5">Full Name</label>
              <div className="relative">
                <FiUser size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input name="name" type="text" value={form.name} onChange={handleChange}
                  placeholder="John Doe" autoComplete="name"
                  className="input pl-10" required />
              </div>
            </div>

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
              <label className="block text-xs font-semibold text-gray-600 mb-1.5">Password</label>
              <div className="relative">
                <FiLock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input name="password" type={showPw ? 'text' : 'password'} value={form.password}
                  onChange={handleChange} placeholder="Min. 6 characters" autoComplete="new-password"
                  className="input pl-10 pr-10" required />
                <button type="button" onClick={() => setShowPw((s) => !s)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  {showPw ? <FiEyeOff size={16} /> : <FiEye size={16} />}
                </button>
              </div>
              {/* Password strength hints */}
              {form.password && (
                <div className="mt-2 space-y-1">
                  {PASSWORD_RULES.map(({ label, test }) => {
                    const passed = test(form.password);
                    return (
                      <div key={label} className={clsx('flex items-center gap-1.5 text-xs transition-colors',
                        passed ? 'text-green-600' : 'text-gray-400')}>
                        <FiCheck size={11} className={passed ? 'text-green-500' : 'text-gray-300'} />
                        {label}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1.5">Confirm Password</label>
              <div className="relative">
                <FiLock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input name="confirm" type={showPw ? 'text' : 'password'} value={form.confirm}
                  onChange={handleChange} placeholder="Re-enter password" autoComplete="new-password"
                  className={clsx('input pl-10',
                    form.confirm && form.confirm !== form.password ? 'border-red-300 focus:ring-red-400' : '')}
                  required />
              </div>
              {form.confirm && form.confirm !== form.password && (
                <p className="text-xs text-red-500 mt-1">Passwords do not match</p>
              )}
            </div>

            {/* Terms */}
            <p className="text-xs text-gray-400 text-center">
              By creating an account you agree to our{' '}
              <span className="text-primary-600 cursor-pointer">Terms of Service</span> and{' '}
              <span className="text-primary-600 cursor-pointer">Privacy Policy</span>.
            </p>

            <button type="submit" disabled={loading}
              className="btn-primary w-full py-3 text-base gap-2">
              {loading ? 'Creating account…' : <>Create Account <FiArrowRight size={18} /></>}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-primary-600 font-semibold hover:text-primary-700 transition-colors">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
