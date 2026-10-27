'use client';

export const dynamic = 'force-dynamic';

import React from 'react';
import { useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { cn } from '@/lib/utils';
import { 
  SlidersHorizontal, 
  AlertTriangle, 
  Shield, 
  Users, 
  Key,
  Database,
  Bell,
  Save,
  RefreshCw,
  Eye,
  EyeOff
} from 'lucide-react';

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<'scoring' | 'rules' | 'benchmarks' | 'system' | 'notifications'>('scoring');
  const [scoringConfig, setScoringConfig] = useState({
    benchmark_outperformance: { weight: 0.30, max_points: 30 },
    category_ranking: { weight: 0.20, max_points: 20 },
    consistency_of_returns: { weight: 0.20, max_points: 20 },
    drawdown_control: { weight: 0.15, max_points: 15 },
    volatility_adjusted: { weight: 0.15, max_points: 15 },
    penalty_per_month: 2.0,
    penalty_cap: 20.0,
  });
  const [rulesConfig, setRulesConfig] = useState([
    { id: 'underperform_3m', enabled: true, severity: 'medium', threshold: 3, overrides: {} },
    { id: 'underperform_6m', enabled: true, severity: 'high', threshold: 6, overrides: {} },
    { id: 'below_top25_category', enabled: true, severity: 'medium', threshold: 75, overrides: {} },
    { id: 'below_top50_category', enabled: true, severity: 'high', threshold: 50, overrides: {} },
    { id: 'rank_decline', enabled: true, severity: 'medium', threshold: 10, overrides: {} },
    { id: 'benchmark_deviation', enabled: true, severity: 'low', threshold: 5, overrides: { 'Small Cap': 10, 'Mid Cap': 8 } },
    { id: 'high_drawdown', enabled: true, severity: 'medium', threshold: 20, overrides: {} },
    { id: 'high_volatility', enabled: true, severity: 'low', threshold: 25, overrides: {} },
    { id: 'consecutive_underperf', enabled: true, severity: 'medium', threshold: 4, overrides: {} },
  ]);
  const [benchmarkMappings] = useState([
    { scheme_code: 'INF204K01VX3', scheme_name: 'HDFC Top 100 Fund', benchmark: 'NIFTY100_TRI' },
    { scheme_code: 'INF767K01EW8', scheme_name: 'PPFAS Flexi Cap Fund', benchmark: 'NIFTY500_TRI' },
    { scheme_code: 'INF179K01BE2', scheme_name: 'HDFC Mid-Cap Opportunities', benchmark: 'NIFTY_MIDCAP150_TRI' },
    { scheme_code: 'INF090I01239', scheme_name: 'SBI Small Cap Fund', benchmark: 'NIFTY_SMALLCAP250_TRI' },
    { scheme_code: 'INF843K01AB1', scheme_name: 'ICICI Pru Large & Mid Cap', benchmark: 'NIFTY_LARGEMIDCAP250_TRI' },
    { scheme_code: 'INF247L01AH0', scheme_name: 'ICICI Pru Equity & Debt', benchmark: 'CRISIL_HYBRID_35_65' },
    { scheme_code: 'INF109K01WO3', scheme_name: 'HDFC Ultra Short Term', benchmark: 'CRISIL_SHORT_TERM_BOND' },
    { scheme_code: 'INF336L01018', scheme_name: 'Motilal Oswal S&P 500 Index', benchmark: 'SP500_TRI' },
  ]);
  const [newBenchmarkMapping, setNewBenchmarkMapping] = useState({ scheme_code: '', scheme_name: '', benchmark: '' });
  const [showAddMapping, setShowAddMapping] = useState(false);

  const tabs = [
    { id: 'scoring', label: 'Scoring Weights', icon: SlidersHorizontal },
    { id: 'rules', label: 'Alert Rules', icon: AlertTriangle },
    { id: 'benchmarks', label: 'Benchmark Mappings', icon: Database },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'system', label: 'System', icon: Shield },
  ];

  const COMPONENT_KEYS = [
    'benchmark_outperformance',
    'category_ranking',
    'consistency_of_returns',
    'drawdown_control',
    'volatility_adjusted',
  ] as const;

  type ComponentKey = typeof COMPONENT_KEYS[number];

  const handleWeightChange = (component: ComponentKey, field: 'weight' | 'max_points', value: number) => {
    const totalWeight = COMPONENT_KEYS
      .filter(k => k !== component)
      .reduce((sum, k) => sum + (scoringConfig[k]?.weight || 0), 0);
    
    if (field === 'weight' && totalWeight + value > 1) {
      alert('Total weights cannot exceed 100%');
      return;
    }

    setScoringConfig(prev => ({
      ...prev,
      [component]: { ...prev[component as keyof typeof scoringConfig], [field]: value },
    }));
  };

  const handleRuleChange = (ruleId: string, field: string, value: any) => {
    setRulesConfig(prev => prev.map(r => r.id === ruleId ? { ...r, [field]: value } : r));
  };

  const handleOverrideChange = (ruleId: string, category: string, value: string) => {
    setRulesConfig(prev => prev.map(r => {
      if (r.id !== ruleId) return r;
      const overrides = { ...r.overrides };
      if (value) overrides[category] = parseFloat(value);
      else delete overrides[category];
      return { ...r, overrides };
    }));
  };

  const addBenchmarkMapping = () => {
    if (!newBenchmarkMapping.scheme_code || !newBenchmarkMapping.benchmark) {
      alert('Please fill all fields');
      return;
    }
    // In real app, would call API
    setShowAddMapping(false);
    setNewBenchmarkMapping({ scheme_code: '', scheme_name: '', benchmark: '' });
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-neutral-900">Settings</h1>
            <p className="text-neutral-500 mt-1">Configure scoring weights, alert rules, and system settings</p>
          </div>
          <Button>
            <Save className="w-4 h-4 mr-1" />
            Save Changes
          </Button>
        </div>

        {/* Tabs */}
        <div className="border-b border-neutral-200">
          <nav className="flex gap-1" role="tablist">
            {tabs.map(tab => (
              <button
                key={tab.id}
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
                  activeTab === tab.id
                    ? 'border-primary-600 text-primary-600'
                    : 'border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300'
                )}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Scoring Weights Tab */}
        {activeTab === 'scoring' && (
          <div className="space-y-6">
            <Card>
              <CardHeader className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <SlidersHorizontal className="w-5 h-5 text-primary-600" />
                  Scoring Engine Weights
                </CardTitle>
                <Badge variant="info">Version 1.0 • Effective 2024-01-01</Badge>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {Object.entries(scoringConfig).map(([key, config]) => {
                    if (key === 'penalty_per_month' || key === 'penalty_cap') return null;
                    const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    return (
                      <Card key={key} className="p-4" variant="bordered">
                        <h4 className="font-medium text-neutral-900 mb-4">{label}</h4>
                        <div className="space-y-4">
                          <div>
                            <label className="block text-sm font-medium text-neutral-700 mb-1">Weight ({config.weight * 100}%)</label>
                            <input
                              type="range"
                              min="0"
                              max="1"
                              step="0.01"
                              value={config.weight}
                              onChange={e => handleWeightChange(key, 'weight', parseFloat(e.target.value))}
                              className="w-full"
                            />
                            <div className="flex justify-between text-xs text-neutral-500 mt-1">
                              <span>0%</span>
                              <span>{(config.weight * 100).toFixed(0)}%</span>
                              <span>100%</span>
                            </div>
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-neutral-700 mb-1">Max Points</label>
                            <Input
                              type="number"
                              value={config.max_points}
                              onChange={e => handleWeightChange(key, 'max_points', parseInt(e.target.value))}
                              min="0"
                              max="100"
                            />
                          </div>
                        </div>
                      </Card>
                    );
                  })}
                </div>

                <Card variant="bordered" className="p-4">
                  <h4 className="font-medium text-neutral-900 mb-4">Penalty Settings</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-neutral-700 mb-1">Penalty per Underperformance Month</label>
                      <Input
                        type="number"
                        step="0.5"
                        value={scoringConfig.penalty_per_month}
                        onChange={e => setScoringConfig(prev => ({ ...prev, penalty_per_month: parseFloat(e.target.value) }))}
                        min="0"
                        max="10"
                        step="0.5"
                      />
                      <p className="text-xs text-neutral-500 mt-1">Points deducted per consecutive underperformance month</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-neutral-700 mb-1">Penalty Cap</label>
                      <Input
                        type="number"
                        value={scoringConfig.penalty_cap}
                        onChange={e => setScoringConfig(prev => ({ ...prev, penalty_cap: parseInt(e.target.value) }))}
                        min="0"
                        max="50"
                      />
                      <p className="text-xs text-neutral-500 mt-1">Maximum total penalty points</p>
                    </div>
                  </div>
                </Card>

                <div className="flex justify-end pt-4 border-t border-neutral-200">
                  <Button variant="secondary" onClick={() => setScoringConfig({
                    benchmark_outperformance: { weight: 0.30, max_points: 30 },
                    category_ranking: { weight: 0.20, max_points: 20 },
                    consistency_of_returns: { weight: 0.20, max_points: 20 },
                    drawdown_control: { weight: 0.15, max_points: 15 },
                    volatility_adjusted: { weight: 0.15, max_points: 15 },
                    penalty_per_month: 2.0,
                    penalty_cap: 20.0,
                  })}>
                    <RefreshCw className="w-4 h-4 mr-1" />
                    Reset to Defaults
                  </Button>
                  <Button className="ml-2">
                    <Save className="w-4 h-4 mr-1" />
                    Save Scoring Config
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
            )}

        {/* Alert Rules Tab */}
        {activeTab === 'rules' && (
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-warning-600" />
                  Alert Rules Configuration
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-neutral-200">
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Rule</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Type</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Severity</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Threshold</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Category Overrides</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-100">
                      {rulesConfig.map(rule => (
                        <tr key={rule.id} className="hover:bg-neutral-50">
                          <td className="px-4 py-3">
                            <div className="font-medium text-neutral-900">{rule.id}</div>
                          </td>
                          <td className="px-4 py-3">
                            <Badge variant="neutral" size="sm">{rule.id.replace(/_/g, ' ')}</Badge>
                          </td>
                          <td className="px-4 py-3">
                            <Select
                              value={rule.severity}
                              onChange={e => handleRuleChange(rule.id, 'severity', e.target.value)}
                              options={[
                                { value: 'low', label: 'Low' },
                                { value: 'medium', label: 'Medium' },
                                { value: 'high', label: 'High' },
                              ]}
                              className="w-[120px]"
                            />
                          </td>
                          <td className="px-4 py-3">
                            <Input
                              type="number"
                              value={rule.threshold}
                              onChange={e => handleRuleChange(rule.id, 'threshold', parseFloat(e.target.value))}
                              min="0"
                              step="0.5"
                              className="w-24"
                            />
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap gap-1">
                              {Object.entries(rule.overrides).map(([cat, val]) => (
                                <span key={cat} className="px-2 py-1 text-xs bg-primary-50 text-primary-700 rounded">
                                  {cat}: {val}
                                </span>
                              ))}
                              <button
                                onClick={() => {
                                  const cat = prompt('Category name:');
                                  const val = prompt('Threshold value:');
                                  if (cat && val) handleOverrideChange(rule.id, cat, val);
                                }}
                                className="text-xs text-primary-600 hover:underline"
                              >
                                + Add
                              </button>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={rule.enabled}
                                onChange={e => handleRuleChange(rule.id, 'enabled', e.target.checked)}
                                className="w-4 h-4 rounded border-neutral-300 text-primary-600 focus:ring-primary-500"
                              />
                              <span className="text-sm text-neutral-700">{rule.enabled ? 'Enabled' : 'Disabled'}</span>
                            </label>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Benchmark Mappings Tab */}
        {activeTab === 'benchmarks' && (
          <div className="space-y-4">
            <Card>
              <CardHeader className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Database className="w-5 h-5 text-primary-600" />
                  Explicit Benchmark Mappings
                </CardTitle>
                <Button onClick={() => setShowAddMapping(true)} size="sm">
                  <span className="w-4 h-4 mr-1">+</span> Add Mapping
                </Button>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-neutral-200">
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Scheme Code</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Scheme Name</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Benchmark</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-100">
                      {benchmarkMappings.map((mapping, index) => (
                        <tr key={mapping.scheme_code} className="hover:bg-neutral-50">
                          <td className="px-4 py-3 font-mono text-sm text-neutral-900">{mapping.scheme_code}</td>
                          <td className="px-4 py-3 text-sm text-neutral-900">{mapping.scheme_name}</td>
                          <td className="px-4 py-3">
                            <Badge variant="info" size="sm">{mapping.benchmark}</Badge>
                          </td>
                          <td className="px-4 py-3">
                            <button className="text-primary-600 hover:underline text-sm">Edit</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {showAddMapping && (
              <Card variant="bordered" className="p-6">
                <h4 className="font-medium text-neutral-900 mb-4">Add New Benchmark Mapping</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Input
                    label="Scheme Code"
                    value={newBenchmarkMapping.scheme_code}
                    onChange={e => setNewBenchmarkMapping({ ...newBenchmarkMapping, scheme_code: e.target.value })}
                    placeholder="e.g., INF204K01VX3"
                  />
                  <Input
                    label="Scheme Name"
                    value={newBenchmarkMapping.scheme_name}
                    onChange={e => setNewBenchmarkMapping({ ...newBenchmarkMapping, scheme_name: e.target.value })}
                    placeholder="e.g., HDFC Top 100 Fund"
                  />
                  <Select
                    label="Benchmark"
                    value={newBenchmarkMapping.benchmark}
                    onChange={e => setNewBenchmarkMapping({ ...newBenchmarkMapping, benchmark: e.target.value })}
                    options={[
                      { value: 'NIFTY100_TRI', label: 'Nifty 100 TRI' },
                      { value: 'NIFTY500_TRI', label: 'Nifty 500 TRI' },
                      { value: 'NIFTY_MIDCAP150_TRI', label: 'Nifty Midcap 150 TRI' },
                      { value: 'NIFTY_SMALLCAP250_TRI', label: 'Nifty Smallcap 250 TRI' },
                      { value: 'NIFTY_LARGEMIDCAP250_TRI', label: 'Nifty LargeMidcap 250 TRI' },
                      { value: 'CRISIL_HYBRID_35_65', label: 'CRISIL Hybrid 35+65' },
                      { value: 'CRISIL_SHORT_TERM_BOND', label: 'CRISIL Short Term Bond' },
                      { value: 'SP500_TRI', label: 'S&P 500 TRI' },
                    ]}
                  />
                </div>
                <div className="flex justify-end gap-2 mt-4">
                  <Button variant="secondary" onClick={() => setShowAddMapping(false)}>Cancel</Button>
                  <Button onClick={addBenchmarkMapping}>Add Mapping</Button>
                </div>
              </Card>
            )}
          </div>
        )}

        {/* Notifications Tab */}
        {activeTab === 'notifications' && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Bell className="w-5 h-5 text-primary-600" />
                  Notification Settings
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {[
                    { key: 'email_high', label: 'Email - High Severity Alerts', default: true },
                    { key: 'email_medium', label: 'Email - Medium Severity Alerts', default: true },
                    { key: 'email_low', label: 'Email - Low Severity Alerts', default: false },
                    { key: 'whatsapp_high', label: 'WhatsApp - High Severity Alerts', default: true },
                    { key: 'whatsapp_medium', label: 'WhatsApp - Medium Severity Alerts', default: false },
                    { key: 'whatsapp_low', label: 'WhatsApp - Low Severity Alerts', default: false },
                    { key: 'daily_digest', label: 'Daily Digest Email', default: true },
                    { key: 'weekly_summary', label: 'Weekly Summary Report', default: true },
                  ].map(item => (
                    <label key={item.key} className="flex items-center justify-between p-4 rounded-lg bg-neutral-50 hover:bg-neutral-100 transition-colors cursor-pointer">
                      <div>
                        <p className="font-medium text-neutral-900">{item.label}</p>
                        <p className="text-sm text-neutral-500">Receive {item.label.toLowerCase()}</p>
                      </div>
                      <input
                        type="checkbox"
                        defaultChecked={item.default}
                        className="w-5 h-5 rounded border-neutral-300 text-primary-600 focus:ring-primary-500"
                      />
                    </label>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* System Tab */}
        {activeTab === 'system' && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="w-5 h-5 text-primary-600" />
                  Database Configuration
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Input label="Database URL" type="password" placeholder="postgresql://user:pass@host:5432/db" />
                  <Input label="Supabase URL" placeholder="https://your-project.supabase.co" />
                  <Input label="Supabase Anon Key" type="password" />
                  <Input label="Supabase Service Role Key" type="password" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Key className="w-5 h-5 text-primary-600" />
                  API & Security
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Input label="JWT Secret" type="password" placeholder="Your JWT signing secret" />
                  <Input label="API Key Salt" type="password" placeholder="Salt for API key hashing" />
                  <Input label="Allowed Origins (CORS)" placeholder="https://mfd.yourdomain.com,https://app.yourdomain.com" />
                  <div className="flex items-center gap-4">
                    <Input label="Rate Limit (req/min)" type="number" defaultValue="100" min="10" max="1000" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="w-5 h-5 text-primary-600" />
                  User Management
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-neutral-200">
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Name</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Email</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Role</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Status</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Last Login</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-100">
                      {[
                        { name: 'Admin User', email: 'admin@mfd.com', role: 'Admin', status: 'Active', lastLogin: '2024-01-15 10:30' },
                        { name: 'Analyst 1', email: 'analyst1@mfd.com', role: 'Analyst', status: 'Active', lastLogin: '2024-01-15 09:15' },
                        { name: 'Analyst 2', email: 'analyst2@mfd.com', role: 'Analyst', status: 'Active', lastLogin: '2024-01-14 16:45' },
                        { name: 'Viewer 1', email: 'viewer@mfd.com', role: 'Viewer', status: 'Inactive', lastLogin: '2024-01-10 14:20' },
                      ].map((user, i) => (
                        <tr key={i} className="hover:bg-neutral-50">
                          <td className="px-4 py-3 font-medium text-neutral-900">{user.name}</td>
                          <td className="px-4 py-3 text-sm text-neutral-600">{user.email}</td>
                          <td className="px-4 py-3">
                            <Badge variant={user.role === 'Admin' ? 'danger' : user.role === 'Analyst' ? 'warning' : 'info'} size="sm">
                              {user.role}
                            </Badge>
                          </td>
                          <td className="px-4 py-3">
                            <Badge variant={user.status === 'Active' ? 'success' : 'neutral'} size="sm" dot>
                              {user.status}
                            </Badge>
                          </td>
                          <td className="px-4 py-3 text-sm text-neutral-600">{user.lastLogin}</td>
                          <td className="px-4 py-3">
                            <button className="text-primary-600 hover:underline text-sm mr-2">Edit</button>
                            <button className="text-danger-600 hover:underline text-sm">Deactivate</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex justify-end mt-4">
                  <Button variant="outline">Add User</Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}