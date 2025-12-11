import React, { useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

const OAuthCallback = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const processedRef = useRef(false);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const code = params.get('code');
    const error = params.get('error');

    if (processedRef.current) return;
    processedRef.current = true;

    if (error) {
      alert('Google Auth Failed');
      navigate('/');
      return;
    }

    if (code) {
      fetch('/api/voice/google_callback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ code }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.success) {
            alert('Calendar Connected Successfully!');
          } else {
            alert(`Failed to connect calendar: ${data.message}`);
          }
          navigate('/');
        })
        .catch(() => {
          alert('Failed to connect calendar');
          navigate('/');
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
