import React, { useEffect } from 'react';

export default function OAuthCallbackPage() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const error = params.get('error');

    if (token) {
      localStorage.setItem('token', token);
      localStorage.removeItem('user');
      window.location.href = '/';
    } else {
      const reason = error || 'google_login_failed';
      window.location.href = `/login?error=${encodeURIComponent(reason)}`;
    }
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center text-gray-500">
      <p>Completing Google sign-in...</p>
    </div>
  );
}
