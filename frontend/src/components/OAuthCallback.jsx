import React, { useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../services/api';

const OAuthCallback = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const calledRef = useRef(false); // Prevent double-fire in React Strict Mode

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const code = params.get('code');
    const error = params.get('error');

    if (error) {
      console.error('Google Auth error:', error);
      alert('Google Auth Failed');
      navigate('/login');
      return;
    }

    // Check if code exists AND if we haven't called it yet
    if (code && !calledRef.current) {
      calledRef.current = true; // Mark as called immediately

      api.post('/api/auth/google', { code })
        .then((res) => {
          localStorage.setItem('token', res.data.token);
          alert('Login successful!');
          navigate('/dashboard');
        })
        .catch((err) => {
          console.error('Login failed:', err);
          alert('Login failed. Please try again.');
          navigate('/login');
        });
    }
  }, [location, navigate]);

  return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-xl font-semibold animate-pulse">Connecting to Google Calendar...</div>
    </div>
  );
};

export default OAuthCallback;
