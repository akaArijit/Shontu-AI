'use client';

export const dynamic = 'force-dynamic';

import React from 'react';
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { cn, formatDate } from '@/lib/utils';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { Upload, Download, FileText, CheckCircle, AlertCircle, Loader2, Trash2, Eye } from 'lucide-react';
import { api } from '@/lib/api';
import { Alert } from '@/types';

interface CSVPreviewRow {
  scheme_code?: string;
  scheme_name?: string;
  amc?: string;
  category?: string;
  benchmark_index?: string;
  short_name?: string;
}

interface CSVError {
  alert_id: string;
  scheme_code: string;
  scheme_name: string;
  category: string;
  alert_type: string;
  severity: 'high' | 'medium' | 'low';
  triggered_on: string;
  details: {
    rule_id: string;
    condition: string;
    feature_values: Record<string, unknown> & { row?: number };
  };
}

export default function CSVUploadPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<CSVPreviewRow[]>([]);
  const [errors, setErrors] = useState<CSVError[]>([]);
  const [showPreview, setShowPreview] = useState(false);
  const [dryRun, setDryRun] = useState(true);
  const [overwrite, setOverwrite] = useState(false);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      if (dryRun) formData.append('dry_run', 'true');
      if (overwrite) formData.append('overwrite', 'true');

      const response = await api.uploadSchemeMasterCSV(file, dryRun);
      return response;
    },
    onSuccess: (data) => {
      setPreviewData(data.preview || []);
      setErrors(data.errors.map((e) => ({
        alert_id: `err_${e.row}`,
        scheme_code: `ROW_${e.row}`,
        scheme_name: 'CSV Row Error',
        category: 'Validation',
        alert_type: 'data_error',
        severity: 'high' as const,
        triggered_on: new Date().toISOString().split('T')[0],
        details: { rule_id: 'csv_validation', condition: e.error, feature_values: e.data },
      })));
      setShowPreview(true);
    },
    onError: (error: Error) => {
      console.error('Upload failed:', error);
    },
  });

  const downloadTemplate = async () => {
    try {
      const blob = await api.downloadBenchmarkTemplate();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'scheme_master_template.csv';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to download template:', error);
    }
  };

  const downloadExport = async () => {
    try {
      const blob = await api.downloadSchemeMaster();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `scheme_master_export_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to download export:', error);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setErrors([]);
      setPreviewData([]);
      setShowPreview(false);
    }
  };

  const handleUpload = () => {
    if (selectedFile) {
      uploadMutation.mutate(selectedFile);
    }
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setPreviewData([]);
    setErrors([]);
    setShowPreview(false);
  };

  const formatDate = (dateStr: string) => new Date(dateStr).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Scheme Master Upload</h1>
          <p className="text-neutral-500 mt-1">Upload scheme master CSV files for deduplication and benchmark mapping</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={downloadTemplate} size="sm">
            <Download className="w-4 h-4 mr-1" />
            Download Template
          </Button>
          <Button onClick={downloadExport} size="sm">
            <Download className="w-4 h-4 mr-1" />
            Export Current
          </Button>
        </div>
      </div>

      {/* Upload Zone */}
      <div className="bg-white rounded-xl border border-neutral-200">
        <div className="p-6 border-b border-neutral-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-neutral-900 flex items-center gap-2">
              <FileText className="w-5 h-5 text-primary-600" />
              Upload Scheme Master CSV
            </h3>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                  className="w-4 h-4 rounded border-neutral-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-neutral-700">Dry run (validate only)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={overwrite}
                  onChange={(e) => setOverwrite(e.target.checked)}
                  className="w-4 h-4 rounded border-neutral-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-neutral-700">Overwrite existing</span>
              </label>
            </div>
          </div>

          {!selectedFile ? (
            <div
              className="border-2 border-dashed border-neutral-300 rounded-lg p-12 text-center hover:border-primary-400 hover:bg-primary-50 transition-colors cursor-pointer"
              onClick={() => document.getElementById('csv-file-input')?.click()}
            >
              <input
                id="csv-file-input"
                type="file"
                accept=".csv"
                onChange={(e) => handleFileSelect(e)}
                className="hidden"
              />
              <FileText className="w-12 h-12 text-neutral-300 mx-auto mb-4" />
              <p className="text-lg font-medium text-neutral-700">Drag & drop CSV file here</p>
              <p className="text-sm text-neutral-500 mt-1">or click to browse</p>
              <p className="text-xs text-neutral-400 mt-2">Accepts .csv files up to 10MB</p>
            </div>
          ) : (
            <div className="flex items-center justify-between p-4 bg-primary-50 rounded-lg border border-primary-100">
              <div className="flex items-center gap-3">
                <FileText className="w-8 h-8 text-primary-600" />
                <div>
                  <p className="font-medium text-neutral-900">{selectedFile.name}</p>
                  <p className="text-sm text-neutral-500">{(selectedFile.size / 1024).toFixed(1)} KB</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" onClick={handleRemoveFile} size="sm">
                  <Trash2 className="w-4 h-4 mr-1" />
                  Remove
                </Button>
                <Button onClick={handleUpload} disabled={uploadMutation.isPending} className="ml-2">
                  <Loader2 className={cn('w-4 h-4 mr-1', uploadMutation.isPending && 'animate-spin')} />
                  {uploadMutation.isPending ? 'Processing...' : 'Upload & Validate'}
                </Button>
              </div>
            </div>
          )}
        </div>

        {showPreview && (
          <div className="p-6 border-t border-neutral-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-neutral-900">Validation Results</h3>
              <div className="flex items-center gap-4 text-sm">
                <Badge variant="success" className="gap-1">
                  <CheckCircle className="w-3.5 h-3.5" />
                  {uploadMutation.data?.valid_rows || 0} Valid
                </Badge>
                {uploadMutation.data && uploadMutation.data.invalid_rows > 0 && (
                  <Badge variant="danger" className="gap-1">
                    <AlertCircle className="w-3.5 h-3.5" />
                    {uploadMutation.data.invalid_rows} Invalid
                  </Badge>
                )}
                <Badge variant="neutral" className="gap-1">
                  <FileText className="w-3.5 h-3.5" />
                  {uploadMutation.data?.total_rows || 0} Total
                </Badge>
              </div>
            </div>

            {/* Errors Table */}
            {errors.length > 0 && (
              <div className="mb-6">
                <h4 className="font-medium text-neutral-900 mb-3">Validation Errors ({errors.length})</h4>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-neutral-200">
                        <th className="px-4 py-2 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Row</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Error</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Data</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-100">
                      {errors.slice(0, 20).map((error, i) => (
                        <tr key={i} className="hover:bg-neutral-50">
                          <td className="px-4 py-2 text-sm font-mono text-neutral-600">{error.details?.feature_values?.row || i + 1}</td>
                          <td className="px-4 py-2 text-sm text-danger-600">{error.details?.condition || 'Unknown error'}</td>
                          <td className="px-4 py-2 text-sm text-neutral-500 font-mono text-xs max-w-xs truncate">
                            {JSON.stringify(error.details?.feature_values || {})}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Preview Table */}
            {previewData.length > 0 && (
              <div>
                <h4 className="font-medium text-neutral-900 mb-3">Preview (First {previewData.length} Rows)</h4>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-neutral-200">
                        <th className="px-4 py-2 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Scheme Code</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Scheme Name</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">AMC</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Category</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Benchmark</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Short Name</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-100">
                      {previewData.map((row, i) => (
                        <tr key={i} className="hover:bg-neutral-50">
                          <td className="px-4 py-3 font-mono text-sm text-neutral-900">{row.scheme_code || '-'}</td>
                          <td className="px-4 py-3 text-sm text-neutral-900">{row.scheme_name || '-'}</td>
                          <td className="px-4 py-3 text-sm text-neutral-600">{row.amc || '-'}</td>
                          <td className="px-4 py-3 text-center">
                            <Badge variant="info" size="sm">{row.category || '-'}</Badge>
                          </td>
                          <td className="px-4 py-3 text-center text-sm text-neutral-600">{row.benchmark_index || '-'}</td>
                          <td className="px-4 py-3 text-center text-sm text-neutral-600">{row.short_name || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Help Section */}
      <div className="bg-white rounded-xl border border-neutral-200 p-6">
        <h3 className="text-lg font-semibold text-neutral-900 mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5 text-primary-600" />
          CSV Format Guide
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-neutral-900 mb-2">Required Columns</h4>
            <ul className="space-y-1 text-sm text-neutral-600 font-mono">
              <li>&bull; scheme_code (unique identifier)</li>
              <li>&bull; scheme_name</li>
              <li>&bull; amc</li>
              <li>&bull; category (must match SEBI categories)</li>
            </ul>
          </div>
          <div>
            <h4 className="font-medium text-neutral-900 mb-2">Optional Columns</h4>
            <ul className="space-y-1 text-sm text-neutral-600 font-mono">
              <li>&bull; sub_category</li>
              <li>&bull; benchmark_index (from predefined list)</li>
              <li>&bull; fund_manager</li>
              <li>&bull; expense_ratio (percentage)</li>
              <li>&bull; aum (in crores)</li>
              <li>&bull; inception_date (YYYY-MM-DD or DD-MM-YYYY)</li>
              <li>&bull; is_active (true/false)</li>
              <li>&bull; short_name (display name)</li>
            </ul>
          </div>
        </div>
        <div className="mt-4 p-4 bg-primary-50 rounded-lg border border-primary-100">
          <h5 className="font-medium text-primary-900 mb-2">Valid SEBI Categories</h5>
          <div className="flex flex-wrap gap-2 text-sm">
            {['Large Cap', 'Flexi Cap', 'Mid Cap', 'Small Cap', 'Large & Mid Cap', 'ELSS', 'Hybrid Aggressive', 'Hybrid Conservative', 'Debt - Ultra Short Duration', 'Debt - Short Duration', 'Debt - Medium Duration', 'International - US', 'International - Global', 'Sectoral - Banking', 'Sectoral - IT', 'Sectoral - Pharma', 'Sectoral - Consumption', 'Sectoral - Infrastructure', 'Thematic'].map((cat) => (
              <Badge key={cat} variant="info" size="sm">{cat}</Badge>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}