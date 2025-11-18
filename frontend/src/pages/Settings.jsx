import React, { useEffect, useState } from 'react';
import { Calendar as CalendarIcon, RefreshCcw } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { calendarService } from '../services/api';

const Settings = () => {
  const { user } = useAuth();
  const [events, setEvents] = useState([]);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState('');

  const loadEvents = async () => {
    try {
      const data = await calendarService.getEvents();
      setEvents(data.events || []);
    } catch (error) {
      console.error('Failed to load calendar events', error);
    }
  };

  useEffect(() => {
    loadEvents();
  }, []);

  const handleSync = async () => {
    setSyncing(true);
    setMessage('');
    try {
      const data = await calendarService.sync();
      setMessage(data.message);
      await loadEvents();
    } catch (error) {
      setMessage('Failed to sync calendar');
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <h2 className="text-xl font-semibold mb-4">Account</h2>
        <p className="text-gray-700">Name: {user?.name}</p>
        <p className="text-gray-700 mt-1">Email: {user?.email}</p>
      </div>

      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold">Calendar Sync</h2>
            <p className="text-sm text-gray-500">Connect to Google Calendar and keep meetings in sync.</p>
          </div>
          <button
            type="button"
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center space-x-2 bg-primary-600 text-white px-3 py-2 rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            <RefreshCcw className="h-4 w-4" />
            <span>{syncing ? 'Syncing…' : 'Sync now'}</span>
          </button>
        </div>
        {message && <p className="text-sm text-gray-600 mb-4">{message}</p>}
        <div className="space-y-3">
          {events.length === 0 ? (
            <p className="text-gray-500">No events synced yet.</p>
          ) : (
            events.map((event) => (
              <div key={event.id} className="flex items-center p-3 bg-gray-50 rounded-lg">
                <CalendarIcon className="h-5 w-5 text-primary-600 mr-3" />
                <div>
                  <p className="font-semibold text-gray-900">{event.title}</p>
                  <p className="text-sm text-gray-500">{new Date(event.start_time).toLocaleString()}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default Settings;
