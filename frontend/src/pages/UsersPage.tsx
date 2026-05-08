import { useState, useEffect, type FormEvent } from 'react';
import { Trash2, Plus, UserPlus, Shield, User as UserIcon } from 'lucide-react';
import { fetchUsers, createUser, updateUser, deleteUser } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import type { User } from '../types';

function RoleBadge({ role }: { role: string }) {
  return role === 'admin' ? (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 dark:text-[#818CF8] bg-indigo-50 dark:bg-[#1E1E3F] border border-indigo-200 dark:border-[#3730A3] rounded px-1.5 py-[2px]">
      <Shield size={10} /> admin
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-gray-500 dark:text-[#94A3B8] bg-gray-100 dark:bg-[#27272F] border border-gray-200 dark:border-[#3F3F47] rounded px-1.5 py-[2px]">
      <UserIcon size={10} /> user
    </span>
  );
}

export default function UsersPage() {
  const { user: currentUser, isAdmin } = useAuth();
  const [users, setUsers]       = useState<User[]>([]);
  const [loading, setLoading]   = useState(true);
  const [showAdd, setShowAdd]   = useState(false);
  const [addEmail, setAddEmail] = useState('');
  const [addName, setAddName]   = useState('');
  const [addPw, setAddPw]       = useState('');
  const [addRole, setAddRole]   = useState<'admin' | 'user'>('user');
  const [addBusy, setAddBusy]   = useState(false);
  const [addError, setAddError] = useState('');

  const load = async () => {
    try { setUsers(await fetchUsers()); } catch { /* requires postgres */ }
    setLoading(false);
  };

  useEffect(() => { void load(); }, []);

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault();
    setAddError('');
    setAddBusy(true);
    try {
      const u = await createUser({ email: addEmail, name: addName, password: addPw, role: addRole });
      setUsers(prev => [...prev, u]);
      setShowAdd(false);
      setAddEmail(''); setAddName(''); setAddPw(''); setAddRole('user');
    } catch (err) {
      setAddError((err as Error).message);
    } finally {
      setAddBusy(false);
    }
  };

  const handleRoleChange = async (id: string, role: 'admin' | 'user') => {
    try {
      const updated = await updateUser(id, { role });
      setUsers(prev => prev.map(u => u.id === id ? updated : u));
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteUser(id);
      setUsers(prev => prev.filter(u => u.id !== id));
    } catch { /* ignore */ }
  };

  if (!isAdmin) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-[#0F0F12]">
        <div className="text-[13px] text-gray-400 dark:text-[#64748B]">Admin access required.</div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50 dark:bg-[#0F0F12] min-h-0">
      {/* Page header */}
      <div className="bg-white dark:bg-[#18181C] border-b border-gray-200 dark:border-[#27272F] px-7 py-[14px]">
        <div className="text-[16px] font-bold text-gray-900 dark:text-[#F1F5F9] tracking-[-0.02em]">Team</div>
        <div className="text-[13px] text-gray-500 dark:text-[#94A3B8] mt-0.5">Manage users and roles</div>
      </div>

      <div className="px-7 py-6 max-w-[760px]">
        <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
          {/* Table header */}
          <div className="px-4 py-[11px] border-b border-gray-200 dark:border-[#27272F] flex items-center justify-between bg-gray-50 dark:bg-[#1E1E24]">
            <span className="text-[11px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">
              Team members
            </span>
            <button
              onClick={() => { setShowAdd(s => !s); setAddError(''); }}
              className="flex items-center gap-1.5 text-[12px] font-medium text-gray-500 dark:text-[#94A3B8] hover:text-gray-700 dark:hover:text-[#F1F5F9] px-2.5 py-[5px] border border-gray-300 dark:border-[#3F3F47] rounded-[5px] bg-white dark:bg-[#18181C] shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-colors"
            >
              <UserPlus size={12} /> Add user
            </button>
          </div>

          {/* Column headers */}
          <div className="flex px-4 py-[7px] bg-gray-50 dark:bg-[#1E1E24] border-b border-gray-200 dark:border-[#27272F]">
            <span className="flex-1 text-[10px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Name / Email</span>
            <span className="w-24 text-[10px] font-semibold text-gray-400 dark:text-[#64748B] uppercase tracking-[0.07em]">Role</span>
            <span className="w-8" />
          </div>

          {loading ? (
            <div className="px-4 py-6 text-[13px] text-gray-400 dark:text-[#64748B] text-center">Loading…</div>
          ) : users.length === 0 ? (
            <div className="px-4 py-6 text-[13px] text-gray-400 dark:text-[#64748B] text-center">
              No users found. Auth requires <code className="font-mono text-[11px]">CHECKPOINT_BACKEND=postgres</code> and <code className="font-mono text-[11px]">JWT_SECRET</code> set.
            </div>
          ) : (
            users.map((u, i) => (
              <div key={u.id} className={`flex items-center gap-2 px-4 py-[10px] ${i < users.length - 1 ? 'border-b border-gray-200 dark:border-[#27272F]' : ''}`}>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-gray-900 dark:text-[#F1F5F9] truncate">{u.name}</div>
                  <div className="text-[11px] text-gray-400 dark:text-[#64748B] truncate">{u.email}</div>
                </div>
                <div className="w-24">
                  {currentUser?.id === u.id ? (
                    <RoleBadge role={u.role} />
                  ) : (
                    <select
                      value={u.role}
                      onChange={e => handleRoleChange(u.id, e.target.value as 'admin' | 'user')}
                      className="text-[12px] font-medium bg-white dark:bg-[#18181C] border border-gray-300 dark:border-[#3F3F47] rounded-[5px] px-1.5 py-[3px] text-gray-700 dark:text-[#CBD5E1] outline-none focus:border-indigo-500 dark:focus:border-[#818CF8] transition-colors cursor-pointer"
                    >
                      <option value="user">user</option>
                      <option value="admin">admin</option>
                    </select>
                  )}
                </div>
                <div className="w-8 flex justify-end">
                  {currentUser?.id !== u.id && (
                    <button
                      onClick={() => handleDelete(u.id)}
                      className="p-[3px] rounded hover:bg-gray-100 dark:hover:bg-[#27272F] text-gray-400 dark:text-[#64748B] hover:text-red-500 dark:hover:text-[#F87171] transition-colors"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              </div>
            ))
          )}

          {/* Add user inline form */}
          {showAdd && (
            <form onSubmit={handleAdd} className="border-t border-gray-200 dark:border-[#27272F] px-4 py-4 bg-gray-50 dark:bg-[#1E1E24] flex flex-col gap-3">
              <div className="text-[12px] font-semibold text-gray-700 dark:text-[#CBD5E1]">Add new user</div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-medium text-gray-500 dark:text-[#94A3B8] mb-1">Name</label>
                  <input value={addName} onChange={e => setAddName(e.target.value)} required placeholder="Full name"
                    className="w-full text-[12px] text-gray-900 dark:text-[#F1F5F9] bg-white dark:bg-[#18181C] border border-gray-300 dark:border-[#3F3F47] rounded-[5px] px-2 py-1.5 outline-none focus:border-indigo-500 dark:focus:border-[#818CF8] transition-all" />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-gray-500 dark:text-[#94A3B8] mb-1">Email</label>
                  <input type="email" value={addEmail} onChange={e => setAddEmail(e.target.value)} required placeholder="email@example.com"
                    className="w-full text-[12px] text-gray-900 dark:text-[#F1F5F9] bg-white dark:bg-[#18181C] border border-gray-300 dark:border-[#3F3F47] rounded-[5px] px-2 py-1.5 outline-none focus:border-indigo-500 dark:focus:border-[#818CF8] transition-all" />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-gray-500 dark:text-[#94A3B8] mb-1">Password</label>
                  <input type="password" value={addPw} onChange={e => setAddPw(e.target.value)} required minLength={8} placeholder="Min 8 chars"
                    className="w-full text-[12px] text-gray-900 dark:text-[#F1F5F9] bg-white dark:bg-[#18181C] border border-gray-300 dark:border-[#3F3F47] rounded-[5px] px-2 py-1.5 outline-none focus:border-indigo-500 dark:focus:border-[#818CF8] transition-all" />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-gray-500 dark:text-[#94A3B8] mb-1">Role</label>
                  <select value={addRole} onChange={e => setAddRole(e.target.value as 'admin' | 'user')}
                    className="w-full text-[12px] bg-white dark:bg-[#18181C] border border-gray-300 dark:border-[#3F3F47] rounded-[5px] px-2 py-1.5 text-gray-900 dark:text-[#F1F5F9] outline-none focus:border-indigo-500 dark:focus:border-[#818CF8] transition-all cursor-pointer">
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>
                </div>
              </div>
              {addError && <div className="text-[11px] text-red-500 dark:text-[#F87171]">{addError}</div>}
              <div className="flex gap-2">
                <button type="submit" disabled={addBusy}
                  className="flex items-center gap-1.5 text-[12px] font-medium text-white bg-indigo-500 dark:bg-[#818CF8] hover:bg-indigo-600 dark:hover:bg-[#6366F1] disabled:opacity-50 px-3 py-1.5 rounded-[5px] transition-colors">
                  <Plus size={12} /> {addBusy ? 'Creating…' : 'Create user'}
                </button>
                <button type="button" onClick={() => setShowAdd(false)}
                  className="text-[12px] font-medium text-gray-500 dark:text-[#94A3B8] hover:text-gray-700 dark:hover:text-[#F1F5F9] px-3 py-1.5 rounded-[5px] transition-colors">
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
