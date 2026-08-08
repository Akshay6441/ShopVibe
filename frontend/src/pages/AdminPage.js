import React, { useEffect, useState, useCallback } from 'react';
import { FiPackage, FiShoppingBag, FiUsers, FiDollarSign, FiPlus, FiEdit2,
         FiTrash2, FiX, FiSave, FiSearch, FiRefreshCw, FiAlertCircle,
         FiCloud, FiShield, FiMessageSquare, FiSend, FiTool } from 'react-icons/fi';
import { getProducts, createProduct, updateProduct, deleteProduct, getCategories } from '../api/products';
import { adminGetOrders, adminUpdateOrderStatus, adminGetStats,
         adminSyncOrderToSalesforce } from '../api/orders';
import { getTickets, updateTicketStatus } from '../api/tickets';
import { runAgent } from '../api/ai';
import Spinner from '../components/common/Spinner';
import toast from 'react-hot-toast';
import clsx from 'clsx';

// ── Stat Card ─────────────────────────────────────────────────────────────────
function StatCard({ icon: Icon, label, value, color, sub }) {
  return (
    <div className="card p-5 flex items-center gap-4">
      <div className={clsx('w-12 h-12 rounded-2xl flex items-center justify-center shrink-0', color)}>
        <Icon size={22} className="text-white" />
      </div>
      <div>
        <p className="text-xs text-gray-400 font-medium">{label}</p>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ── Product Form Modal ────────────────────────────────────────────────────────
function ProductModal({ product, categories, onClose, onSaved }) {
  const isEdit = !!product?.id;
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: product?.name || '',
    slug: product?.slug || '',
    description: product?.description || '',
    price: product?.price || '',
    original_price: product?.original_price || '',
    image_url: product?.image_url || '',
    category_id: product?.category?.id || '',
    stock_quantity: product?.stock_quantity ?? 0,
    is_featured: product?.is_featured || false,
    is_active: product?.is_active ?? true,
    brand: product?.brand || '',
    tags: product?.tags || '',
  });

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((f) => ({ ...f, [name]: type === 'checkbox' ? checked : value }));
  };

  // Auto-generate slug from name
  const handleNameChange = (e) => {
    const name = e.target.value;
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    setForm((f) => ({ ...f, name, slug }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.slug || !form.price) {
      toast.error('Name, slug, and price are required'); return;
    }
    setSaving(true);
    const payload = {
      ...form,
      price: parseFloat(form.price),
      original_price: form.original_price ? parseFloat(form.original_price) : null,
      stock_quantity: parseInt(form.stock_quantity, 10),
      category_id: form.category_id ? parseInt(form.category_id, 10) : null,
    };
    try {
      if (isEdit) {
        await updateProduct(product.id, payload);
        toast.success('Product updated!');
      } else {
        await createProduct(payload);
        toast.success('Product created!');
      }
      onSaved();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const fields = [
    { name: 'name',           label: 'Product Name *',   type: 'text',   onChange: handleNameChange, half: false },
    { name: 'slug',           label: 'Slug *',           type: 'text',   half: false },
    { name: 'price',          label: 'Price ($) *',      type: 'number', half: true },
    { name: 'original_price', label: 'Original Price ($)',type: 'number', half: true },
    { name: 'image_url',      label: 'Image URL',        type: 'url',    half: false },
    { name: 'brand',          label: 'Brand',            type: 'text',   half: true },
    { name: 'stock_quantity', label: 'Stock Qty',        type: 'number', half: true },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto animate-slide-up">
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <h2 className="font-bold text-gray-900 text-lg">{isEdit ? 'Edit Product' : 'Add New Product'}</h2>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-gray-100 transition-colors">
            <FiX size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            {fields.map(({ name, label, type, onChange, half }) => (
              <div key={name} className={clsx(!half && 'sm:col-span-2')}>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">{label}</label>
                <input name={name} type={type} value={form[name]}
                  onChange={onChange || handleChange}
                  step={type === 'number' ? '0.01' : undefined}
                  className="input text-sm" />
              </div>
            ))}
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1.5">Category</label>
              <select name="category_id" value={form.category_id} onChange={handleChange} className="input text-sm cursor-pointer">
                <option value="">— None —</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1.5">Tags (comma separated)</label>
              <input name="tags" type="text" value={form.tags} onChange={handleChange}
                placeholder="sale, new, trending" className="input text-sm" />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-gray-600 mb-1.5">Description</label>
              <textarea name="description" value={form.description} onChange={handleChange}
                rows={3} className="input text-sm resize-none" />
            </div>
            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" name="is_featured" checked={form.is_featured} onChange={handleChange}
                  className="w-4 h-4 accent-primary-600 rounded" />
                <span className="text-sm text-gray-700 font-medium">Featured</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" name="is_active" checked={form.is_active} onChange={handleChange}
                  className="w-4 h-4 accent-primary-600 rounded" />
                <span className="text-sm text-gray-700 font-medium">Active</span>
              </label>
            </div>
          </div>
          <div className="flex gap-3 pt-2 border-t border-gray-100">
            <button type="button" onClick={onClose} className="btn-secondary flex-1 py-2.5">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary flex-1 py-2.5 gap-2">
              <FiSave size={15} /> {saving ? 'Saving…' : isEdit ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Products Tab ──────────────────────────────────────────────────────────────
function ProductsTab({ categories }) {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [modalProduct, setModalProduct] = useState(null); // null = closed, {} = new, {...} = edit
  const [deleting, setDeleting] = useState(null);

  const fetchProducts = useCallback(() => {
    setLoading(true);
    getProducts({ per_page: 100 })
      .then((r) => setProducts(r.data.items))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const handleDelete = async (product) => {
    if (!window.confirm(`Delete "${product.name}"? This cannot be undone.`)) return;
    setDeleting(product.id);
    try {
      await deleteProduct(product.id);
      toast.success('Product deleted');
      fetchProducts();
    } catch {
      toast.error('Delete failed');
    } finally {
      setDeleting(null);
    }
  };

  const filtered = products.filter((p) =>
    !search || p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.brand?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="relative flex-1">
          <FiSearch size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search products…" className="input pl-10 text-sm" />
        </div>
        <button onClick={fetchProducts} className="btn-secondary gap-1.5 text-sm px-4">
          <FiRefreshCw size={14} /> Refresh
        </button>
        <button onClick={() => setModalProduct({})} className="btn-primary gap-1.5 text-sm px-5">
          <FiPlus size={15} /> Add Product
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-100">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {['Product', 'Category', 'Price', 'Stock', 'Status', 'Actions'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <img src={p.image_url || 'https://via.placeholder.com/40'}
                        alt={p.name} className="w-10 h-10 rounded-lg object-cover bg-gray-100 border border-gray-100 shrink-0" />
                      <div>
                        <p className="font-medium text-gray-800 max-w-xs truncate">{p.name}</p>
                        {p.brand && <p className="text-xs text-gray-400">{p.brand}</p>}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{p.category?.name || '—'}</td>
                  <td className="px-4 py-3 font-semibold text-gray-900">
                    ${p.price.toFixed(2)}
                    {p.original_price && (
                      <span className="text-xs text-gray-400 line-through ml-1">${p.original_price.toFixed(2)}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={clsx('font-semibold', p.stock_quantity === 0 ? 'text-red-500' :
                      p.stock_quantity <= 5 ? 'text-orange-500' : 'text-green-600')}>
                      {p.stock_quantity}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-1">
                      <span className={clsx('badge text-xs', p.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500')}>
                        {p.is_active ? 'Active' : 'Inactive'}
                      </span>
                      {p.is_featured && <span className="badge bg-primary-100 text-primary-700 text-xs">Featured</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button onClick={() => setModalProduct(p)}
                        className="p-1.5 rounded-lg text-blue-500 hover:bg-blue-50 transition-colors" title="Edit">
                        <FiEdit2 size={15} />
                      </button>
                      <button onClick={() => handleDelete(p)} disabled={deleting === p.id}
                        className="p-1.5 rounded-lg text-red-400 hover:bg-red-50 transition-colors" title="Delete">
                        {deleting === p.id ? <Spinner size="sm" /> : <FiTrash2 size={15} />}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div className="text-center py-10 text-gray-400">No products found.</div>
          )}
        </div>
      )}

      {modalProduct !== null && (
        <ProductModal product={modalProduct} categories={categories}
          onClose={() => setModalProduct(null)} onSaved={fetchProducts} />
      )}
    </div>
  );
}

// ── Orders Tab ────────────────────────────────────────────────────────────────
const ORDER_STATUSES = ['pending', 'processing', 'shipped', 'delivered', 'cancelled'];
const STATUS_COLORS = {
  pending: 'bg-yellow-100 text-yellow-700', processing: 'bg-blue-100 text-blue-700',
  shipped: 'bg-purple-100 text-purple-700', delivered: 'bg-green-100 text-green-700',
  cancelled: 'bg-red-100 text-red-600',
};

function OrdersTab() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(null);
  const [syncing, setSyncing] = useState(null);

  const fetchOrders = () => {
    setLoading(true);
    adminGetOrders().then((r) => setOrders(r.data)).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(() => { fetchOrders(); }, []);

  const handleSalesforceSync = async (orderId) => {
    setSyncing(orderId);
    try {
      const res = await adminSyncOrderToSalesforce(orderId);
      toast.success(res.data.message || 'Synced to Salesforce');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Salesforce sync failed');
    } finally {
      setSyncing(null);
    }
  };

  const handleStatusChange = async (orderId, status) => {
    setUpdating(orderId);
    try {
      await adminUpdateOrderStatus(orderId, status);
      setOrders((prev) => prev.map((o) => o.id === orderId ? { ...o, status } : o));
      toast.success('Order status updated');
    } catch {
      toast.error('Update failed');
    } finally {
      setUpdating(null);
    }
  };

  return (
    <div>
      <div className="flex justify-end mb-5">
        <button onClick={fetchOrders} className="btn-secondary gap-1.5 text-sm px-4">
          <FiRefreshCw size={14} /> Refresh
        </button>
      </div>
      {loading ? (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-100">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {['Order', 'Customer', 'Items', 'Total', 'Payment', 'Status', 'Fraud', 'Date', 'Actions'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {orders.map((order) => (
                <tr key={order.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-bold text-gray-800">#{order.id}</td>
                  <td className="px-4 py-3 text-gray-600 max-w-[140px] truncate">{order.shipping_address?.split(',')[0]}</td>
                  <td className="px-4 py-3 text-gray-500">{order.items?.length} items</td>
                  <td className="px-4 py-3 font-semibold text-gray-900">${order.total_amount.toFixed(2)}</td>
                  <td className="px-4 py-3">
                    <span className={clsx('badge text-xs', order.payment_status === 'paid'
                      ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700')}>
                      {order.payment_status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="relative">
                      {updating === order.id ? (
                        <Spinner size="sm" />
                      ) : (
                        <select value={order.status}
                          onChange={(e) => handleStatusChange(order.id, e.target.value)}
                          className={clsx('text-xs font-semibold rounded-lg border-0 px-2 py-1 pr-6 cursor-pointer focus:ring-2 focus:ring-primary-400 appearance-none',
                            STATUS_COLORS[order.status] || 'bg-gray-100 text-gray-600')}>
                          {ORDER_STATUSES.map((s) => (
                            <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                          ))}
                        </select>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {order.is_fraud_flagged ? (
                      <span className="badge bg-red-100 text-red-600 text-xs" title={order.fraud_reason || ''}>
                        <FiShield size={11} className="inline mr-1" />Flagged
                      </span>
                    ) : (
                      <span className="text-gray-300 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {new Date(order.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => handleSalesforceSync(order.id)} disabled={syncing === order.id}
                      className="p-1.5 rounded-lg text-emerald-500 hover:bg-emerald-50 transition-colors" title="Sync to Salesforce">
                      {syncing === order.id ? <Spinner size="sm" /> : <FiCloud size={15} />}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {orders.length === 0 && (
            <div className="text-center py-10 text-gray-400">No orders yet.</div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Tickets Tab ───────────────────────────────────────────────────────────────
function TicketsTab() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(null);

  const fetchTickets = () => {
    setLoading(true);
    getTickets().then((r) => setTickets(r.data)).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(() => { fetchTickets(); }, []);

  const handleStatusToggle = async (ticket) => {
    const next = ticket.status === 'resolved' ? 'open' : 'resolved';
    setUpdating(ticket.id);
    try {
      await updateTicketStatus(ticket.id, next);
      setTickets((prev) => prev.map((t) => t.id === ticket.id ? { ...t, status: next } : t));
      toast.success(next === 'resolved' ? 'Ticket resolved' : 'Ticket reopened');
    } catch {
      toast.error('Update failed');
    } finally {
      setUpdating(null);
    }
  };

  return (
    <div>
      <div className="flex justify-end mb-5">
        <button onClick={fetchTickets} className="btn-secondary gap-1.5 text-sm px-4">
          <FiRefreshCw size={14} /> Refresh
        </button>
      </div>
      {loading ? (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      ) : (
        <div className="space-y-3">
          {tickets.map((t) => (
            <div key={t.id} className="flex items-start justify-between gap-4 border border-gray-100 rounded-xl p-4 hover:bg-gray-50 transition-colors">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-semibold text-gray-800 text-sm">#{t.id} · {t.subject}</p>
                  <span className={clsx('badge text-xs', t.status === 'resolved'
                    ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700')}>
                    {t.status}
                  </span>
                  {t.order_id && (
                    <span className="badge bg-gray-100 text-gray-500 text-xs">order #{t.order_id}</span>
                  )}
                </div>
                <p className="text-gray-500 text-sm mt-1">{t.message}</p>
                <p className="text-gray-400 text-xs mt-2">
                  From user #{t.user_id} · {new Date(t.created_at).toLocaleString()}
                </p>
              </div>
              <button onClick={() => handleStatusToggle(t)} disabled={updating === t.id}
                className={clsx('btn text-xs px-3 py-1.5 shrink-0', t.status === 'resolved' ? 'btn-secondary' : 'btn-primary')}>
                {updating === t.id ? <Spinner size="sm" /> : t.status === 'resolved' ? 'Reopen' : 'Resolve'}
              </button>
            </div>
          ))}
          {tickets.length === 0 && (
            <div className="text-center py-10 text-gray-400">No support tickets yet.</div>
          )}
        </div>
      )}
    </div>
  );
}

// ── AI Agent Tab ──────────────────────────────────────────────────────────────
function AIAgentTab() {
  const [instruction, setInstruction] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);

  const handleRun = async (e) => {
    e.preventDefault();
    if (!instruction.trim()) { toast.error('Describe what the agent should do'); return; }
    setRunning(true);
    setResult(null);
    try {
      const res = await runAgent(instruction.trim());
      setResult(res.data);
      toast.success('Agent finished');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Agent failed to run');
    } finally {
      setRunning(false);
    }
  };

  const EXAMPLES = [
    'Inspect order #1 and summarize its status',
    'Flag order #2 as fraudulent — reason: unusual payment method',
    'Advance order #3 to shipped',
    'Draft a friendly response about order #4',
    'Read the latest support ticket',
  ];

  return (
    <div>
      <div className="mb-4">
        <p className="text-sm text-gray-500 mb-2">
          The agent can read orders &amp; tickets and take actions: <strong>flag fraud</strong>,{' '}
          <strong>update status</strong>, and <strong>draft responses</strong>. It replies with a
          summary plus the list of actions it performed.
        </p>
        <div className="flex flex-wrap gap-2 mb-3">
          {EXAMPLES.map((ex) => (
            <button key={ex} onClick={() => setInstruction(ex)}
              className="text-xs px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-200 text-gray-500 hover:bg-primary-50 hover:text-primary-700 hover:border-primary-200 transition-colors">
              {ex}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleRun} className="mb-6">
        <textarea value={instruction} onChange={(e) => setInstruction(e.target.value)}
          rows={3} placeholder="Tell the agent what to do… (e.g. “Check order #1 and flag it if it looks fraudulent”)"
          className="input text-sm resize-none w-full" />
        <div className="flex justify-end mt-3">
          <button type="submit" disabled={running}
            className="btn-primary gap-2 text-sm px-6 py-2.5">
            <FiSend size={15} /> {running ? 'Thinking…' : 'Run Agent'}
          </button>
        </div>
      </form>

      {running && (
        <div className="flex items-center gap-3 text-gray-500 text-sm py-6">
          <Spinner size="md" /> Agent is working…
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="border border-primary-100 bg-primary-50 rounded-xl p-4">
            <p className="text-xs font-semibold text-primary-600 uppercase tracking-wide mb-2">Agent reply</p>
            <p className="text-gray-800 text-sm leading-relaxed">{result.reply}</p>
          </div>
          {result.actions.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Actions taken</p>
              <div className="space-y-2">
                {result.actions.map((a, i) => (
                  <div key={i} className="border border-gray-100 rounded-xl p-3 bg-gray-50">
                    <p className="text-sm font-semibold text-gray-700">
                      <FiTool size={13} className="inline mr-1.5 text-primary-600" />
                      {a.tool}
                      <span className="text-gray-400 font-normal ml-2">{JSON.stringify(a.args)}</span>
                    </p>
                    <pre className="text-xs text-gray-500 mt-1.5 whitespace-pre-wrap font-mono">
                      {JSON.stringify(a.result, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Admin Page ───────────────────────────────────────────────────────────
const TABS = [
  { id: 'products', label: 'Products',   icon: FiPackage },
  { id: 'orders',   label: 'Orders',     icon: FiShoppingBag },
  { id: 'tickets',  label: 'Tickets',    icon: FiMessageSquare },
  { id: 'ai',       label: 'AI Agent',   icon: FiShield },
];

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState('products');
  const [stats, setStats] = useState(null);
  const [categories, setCategories] = useState([]);

  useEffect(() => {
    adminGetStats().then((r) => setStats(r.data)).catch(console.error);
    getCategories().then((r) => setCategories(r.data)).catch(console.error);
  }, []);

  return (
    <div className="bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="bg-gradient-to-r from-primary-700 to-primary-900 text-white py-10">
        <div className="container-page">
          <div className="flex items-center gap-3 mb-1">
            <FiAlertCircle size={20} className="text-primary-300" />
            <span className="text-primary-200 text-sm font-medium">Admin Panel</span>
          </div>
          <h1 className="text-3xl font-display font-bold">Dashboard</h1>
        </div>
      </div>

      <div className="container-page py-8">
        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard icon={FiDollarSign} label="Total Revenue" color="bg-green-500"
            value={stats ? `$${stats.total_revenue.toLocaleString()}` : '—'}
            sub="All time" />
          <StatCard icon={FiShoppingBag} label="Total Orders" color="bg-blue-500"
            value={stats?.total_orders ?? '—'} sub="All time" />
          <StatCard icon={FiPackage} label="Products" color="bg-primary-600"
            value={stats?.total_products ?? '—'} sub="In catalog" />
          <StatCard icon={FiUsers} label="Customers" color="bg-accent-500"
            value={stats?.total_users ?? '—'} sub="Registered" />
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 mb-6 bg-white rounded-xl shadow-card p-1 w-fit">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setActiveTab(id)}
              className={clsx(
                'flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all',
                activeTab === id
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'text-gray-500 hover:text-gray-800 hover:bg-gray-50'
              )}>
              <Icon size={15} /> {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="bg-white rounded-2xl shadow-card p-6">
          {activeTab === 'products' && <ProductsTab categories={categories} />}
          {activeTab === 'orders' && <OrdersTab />}
          {activeTab === 'tickets' && <TicketsTab />}
          {activeTab === 'ai' && <AIAgentTab />}
        </div>
      </div>
    </div>
  );
}
