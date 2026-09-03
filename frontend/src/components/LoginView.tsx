import React, { useState } from 'react';
import { Train, Lock, User as UserIcon, ArrowRight, ShieldCheck, AlertCircle } from 'lucide-react';
import { loginUser } from '../services/api';
import { User } from '../types';

interface LoginViewProps {
  onLoginSuccess: (user: User) => void;
}

export const LoginView: React.FC<LoginViewProps> = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('planner1');
  const [password, setPassword] = useState('planner123');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      setError('Please enter both username and password.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await loginUser(username, password);
      onLoginSuccess(data.user);
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickSelect = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col justify-center items-center p-4 selection:bg-saffron-500 selection:text-white">
      {/* Central Card */}
      <div className="max-w-md w-full bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden">
        {/* Saffron Top Header */}
        <div className="bg-gradient-to-r from-saffron-500 via-saffron-600 to-amber-600 p-8 text-center text-white relative">
          <div className="inline-flex p-3 bg-white/20 backdrop-blur-md rounded-2xl mb-3 shadow-inner">
            <Train className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-2xl font-black tracking-tight">RailBlock AI</h1>
          <p className="text-white/90 text-xs font-medium uppercase tracking-widest mt-1">
            Indian Railways Decision Support Portal
          </p>
        </div>

        {/* Card Body */}
        <div className="p-8">
          <div className="text-center mb-6">
            <h2 className="text-lg font-bold text-navy-950">Authorized Portal Access</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Secure single sign-on for railway traffic controllers and maintenance engineers
            </p>
          </div>

          {error && (
            <div className="mb-5 p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2.5 text-xs text-rose-700">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                Username
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <UserIcon className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter railway username"
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-navy-800 focus:border-navy-800 transition-all font-medium"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-navy-800 focus:border-navy-800 transition-all font-medium"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-3 px-4 bg-navy-800 hover:bg-navy-900 text-white font-bold rounded-xl shadow-lg hover:shadow-navy-800/30 flex items-center justify-center gap-2 transition-all duration-200 text-sm disabled:opacity-50"
            >
              {loading ? (
                <span>Verifying credentials...</span>
              ) : (
                <>
                  <span>Sign In to Dashboard</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Access Badges */}
          <div className="mt-6 pt-5 border-t border-slate-100 text-center">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2.5">
              Instant Demo Role Profiles
            </p>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <button
                type="button"
                onClick={() => handleQuickSelect('planner1', 'planner123')}
                className={`py-2 px-2.5 rounded-lg border text-left transition-all ${
                  username === 'planner1'
                    ? 'border-saffron-500 bg-saffron-50 text-saffron-900 font-bold'
                    : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
                }`}
              >
                <div className="font-bold text-[11px]">Planner</div>
                <div className="text-[9px] text-slate-400 font-mono">planner1</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickSelect('ops1', 'ops123')}
                className={`py-2 px-2.5 rounded-lg border text-left transition-all ${
                  username === 'ops1'
                    ? 'border-saffron-500 bg-saffron-50 text-saffron-900 font-bold'
                    : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
                }`}
              >
                <div className="font-bold text-[11px]">Operations</div>
                <div className="text-[9px] text-slate-400 font-mono">ops1</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickSelect('approver1', 'approver123')}
                className={`py-2 px-2.5 rounded-lg border text-left transition-all ${
                  username === 'approver1'
                    ? 'border-saffron-500 bg-saffron-50 text-saffron-900 font-bold'
                    : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100'
                }`}
              >
                <div className="font-bold text-[11px]">Approver</div>
                <div className="text-[9px] text-slate-400 font-mono">approver1</div>
              </button>
            </div>
          </div>
        </div>

        {/* Security Footer */}
        <div className="bg-slate-50 px-8 py-3.5 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
          <div className="flex items-center gap-1.5 text-navy-800 font-semibold">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>256-Bit Encrypted Portal</span>
          </div>
          <span className="font-mono text-slate-400">Phase 2.0</span>
        </div>
      </div>
    </div>
  );
};
