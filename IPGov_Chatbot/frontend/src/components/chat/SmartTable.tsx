'use client';

import React, { useState, useMemo } from 'react';
import { TabularData, TableColumn } from '@/types/chat';
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Copy,
  Check,
  Download,
  Search,
  ChevronLeft,
  ChevronRight,
  Table as TableIcon,
} from 'lucide-react';

interface SmartTableProps {
  tabularData?: TabularData;
  children?: React.ReactNode;
}

// Hàm trích xuất text thuần từ cây React Nodes
function extractTextFromReactNode(node: any): string {
  if (node === null || node === undefined) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(extractTextFromReactNode).join('');
  if (React.isValidElement(node) && node.props && (node.props as any).children) {
    return extractTextFromReactNode((node.props as any).children);
  }
  return '';
}

// Phân tích thẻ <table> HTML/ReactNode do ReactMarkdown sinh ra khi không có tabularData
function parseTableFromChildren(children: React.ReactNode): { columns: TableColumn[]; rows: Record<string, any>[] } {
  const columns: TableColumn[] = [];
  const rows: Record<string, any>[] = [];

  try {
    React.Children.forEach(children, (child) => {
      if (!React.isValidElement(child)) return;

      const rawType = (child.type as any)?.name || child.type || '';
      const typeName = String(rawType).toLowerCase();

      // Xử lý thead
      if (typeName === 'thead' || typeName.includes('thead')) {
        const theadChildren = (child.props as any)?.children;
        React.Children.forEach(theadChildren, (tr) => {
          if (!React.isValidElement(tr)) return;
          const trChildren = (tr.props as any)?.children;
          React.Children.forEach(trChildren, (th, idx) => {
            if (!React.isValidElement(th)) return;
            const text = extractTextFromReactNode(th).trim();
            const alignAttr = (th.props as any)?.align || 'left';
            const align = alignAttr === 'center' ? 'center' : alignAttr === 'right' ? 'right' : 'left';
            const isBadge = ['trạng thái', 'tình trạng', 'status', 'phê duyệt'].some((k) =>
              text.toLowerCase().includes(k)
            );
            const isNum = ['stt', 'số lượng', 'kinh phí', 'tổng', 'giá trị', 'mục'].some((k) =>
              text.toLowerCase().includes(k)
            );
            columns.push({
              key: `col_${idx}`,
              label: text || `Cột ${idx + 1}`,
              align: isNum && !text.toLowerCase().includes('stt') ? 'right' : align,
              data_type: isBadge ? 'badge' : isNum ? 'number' : 'text',
            });
          });
        });
      }

      // Xử lý tbody
      if (typeName === 'tbody' || typeName.includes('tbody')) {
        const tbodyChildren = (child.props as any)?.children;
        React.Children.forEach(tbodyChildren, (tr, rIdx) => {
          if (!React.isValidElement(tr)) return;
          const trChildren = (tr.props as any)?.children;
          const rowData: Record<string, any> = {};
          let cIdx = 0;
          React.Children.forEach(trChildren, (td) => {
            if (!React.isValidElement(td)) return;
            const text = extractTextFromReactNode(td).trim();
            rowData[`col_${cIdx}`] = text;
            cIdx++;
          });
          if (Object.keys(rowData).length > 0) {
            rows.push(rowData);
          }
        });
      }

      // Xử lý tr trực tiếp (khi không có thead/tbody bao bọc)
      if (typeName === 'tr' || typeName.includes('tr')) {
        const trChildren = (child.props as any)?.children;
        if (columns.length === 0) {
          // Coi dòng tr đầu tiên là header
          React.Children.forEach(trChildren, (cell, idx) => {
            if (!React.isValidElement(cell)) return;
            const text = extractTextFromReactNode(cell).trim();
            columns.push({
              key: `col_${idx}`,
              label: text || `Cột ${idx + 1}`,
              align: 'left',
              data_type: 'text',
            });
          });
        } else {
          // Các dòng tr tiếp theo là dữ liệu
          const rowData: Record<string, any> = {};
          let cIdx = 0;
          React.Children.forEach(trChildren, (cell) => {
            if (!React.isValidElement(cell)) return;
            const text = extractTextFromReactNode(cell).trim();
            rowData[`col_${cIdx}`] = text;
            cIdx++;
          });
          if (Object.keys(rowData).length > 0) {
            rows.push(rowData);
          }
        }
      }
    });
  } catch (err) {
    console.warn('Lỗi phân tích cú pháp HTML table từ ReactMarkdown:', err);
  }

  return { columns, rows };
}

// Render Badge trạng thái tự động hoặc format văn bản
function renderCellContent(value: any, column: TableColumn) {
  if (value === null || value === undefined) return '-';
  const rawStr = String(value).trim();
  const clean = rawStr.replace(/^\*\*|\*\*$/g, '').trim();
  const lower = clean.toLowerCase();

  // Nhận diện Badge trạng thái công vụ
  if (
    column.data_type === 'badge' ||
    ['approved', 'đã phê duyệt', 'hoàn thành', 'thành công', 'active', 'đang kích hoạt'].includes(lower)
  ) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse"></span>
        {clean}
      </span>
    );
  }

  if (['draft', 'bản nháp', 'dự thảo', 'đang thực hiện', 'cần rà soát'].includes(lower)) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 shadow-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mr-1.5"></span>
        {clean}
      </span>
    );
  }

  if (['rejected', 'bị từ chối', 'thất bại', 'inactive', 'tạm dừng'].includes(lower)) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200 shadow-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mr-1.5"></span>
        {clean}
      </span>
    );
  }

  if (['pending', 'chờ phê duyệt', 'chờ duyệt'].includes(lower)) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200 shadow-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mr-1.5"></span>
        {clean}
      </span>
    );
  }

  // Định dạng in đậm nếu có markdown **
  if (rawStr.startsWith('**') && rawStr.endsWith('**')) {
    return <span className="font-semibold text-slate-900">{clean}</span>;
  }

  // Định dạng số
  if (column.data_type === 'number') {
    return <span className="font-mono font-medium text-slate-800">{clean}</span>;
  }

  return <span className="text-slate-700">{clean}</span>;
}

export const SmartTable: React.FC<SmartTableProps> = ({ tabularData, children }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [copied, setCopied] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const PAGE_SIZE = 5;

  // Xác định cấu trúc cột và dòng
  const { columns, rows, title } = useMemo(() => {
    if (tabularData && tabularData.columns && tabularData.columns.length > 0) {
      return {
        columns: tabularData.columns,
        rows: tabularData.rows || [],
        title: tabularData.title,
      };
    }
    const parsed = parseTableFromChildren(children);
    return {
      columns: parsed.columns,
      rows: parsed.rows,
      title: undefined,
    };
  }, [tabularData, children]);

  // Lọc dữ liệu theo từ khóa tìm kiếm
  const filteredRows = useMemo(() => {
    if (!searchTerm.trim()) return rows;
    const term = searchTerm.toLowerCase().trim();
    return rows.filter((r) =>
      Object.values(r).some((val) => String(val ?? '').toLowerCase().includes(term))
    );
  }, [rows, searchTerm]);

  // Sắp xếp dữ liệu theo cột được chọn
  const sortedRows = useMemo(() => {
    if (!sortKey) return filteredRows;
    const colConfig = columns.find((c) => c.key === sortKey);
    const isNum = colConfig?.data_type === 'number';

    return [...filteredRows].sort((a, b) => {
      const valA = a[sortKey];
      const valB = b[sortKey];
      if (valA === valB) return 0;
      if (valA === undefined || valA === null) return 1;
      if (valB === undefined || valB === null) return -1;

      if (isNum) {
        const numA = parseFloat(String(valA).replace(/,/g, '')) || 0;
        const numB = parseFloat(String(valB).replace(/,/g, '')) || 0;
        return sortOrder === 'asc' ? numA - numB : numB - numA;
      }

      const strA = String(valA).toLowerCase();
      const strB = String(valB).toLowerCase();
      return sortOrder === 'asc' ? strA.localeCompare(strB, 'vi') : strB.localeCompare(strA, 'vi');
    });
  }, [filteredRows, sortKey, sortOrder, columns]);

  // Phân trang
  const totalPages = Math.ceil(sortedRows.length / PAGE_SIZE) || 1;
  const paginatedRows = useMemo(() => {
    if (sortedRows.length <= PAGE_SIZE) return sortedRows;
    const start = (currentPage - 1) * PAGE_SIZE;
    return sortedRows.slice(start, start + PAGE_SIZE);
  }, [sortedRows, currentPage, PAGE_SIZE]);

  // Chuyển đổi thứ tự sắp xếp khi click header
  const handleSort = (key: string) => {
    if (sortKey === key) {
      if (sortOrder === 'asc') setSortOrder('desc');
      else {
        setSortKey(null);
        setSortOrder('asc');
      }
    } else {
      setSortKey(key);
      setSortOrder('asc');
    }
  };

  // Sao chép dạng TSV để dán trực tiếp vào Excel
  const handleCopy = () => {
    if (columns.length === 0 || rows.length === 0) return;
    const headerLine = columns.map((c) => c.label).join('\t');
    const rowsLines = sortedRows
      .map((r) => columns.map((c) => String(r[c.key] ?? '').replace(/^\*\*|\*\*$/g, '')).join('\t'))
      .join('\n');
    const tsv = `${headerLine}\n${rowsLines}`;
    navigator.clipboard.writeText(tsv);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Xuất file CSV có UTF-8 BOM chuẩn tiếng Việt
  const handleExportCsv = () => {
    if (columns.length === 0 || rows.length === 0) return;
    const escapeCsv = (str: any) => `"${String(str ?? '').replace(/^\*\*|\*\*$/g, '').replace(/"/g, '""')}"`;
    const headerLine = columns.map((c) => escapeCsv(c.label)).join(',');
    const rowsLines = sortedRows
      .map((r) => columns.map((c) => escapeCsv(r[c.key] ?? '')).join(','))
      .join('\n');
    const csvContent = '\uFEFF' + `${headerLine}\n${rowsLines}`;
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `bang_so_lieu_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Nếu không phân tích được cột nào, render fallback có viền và style đầy đủ
  if (columns.length === 0) {
    return (
      <div className="not-prose my-4 overflow-x-auto rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <table className="w-full text-sm border-collapse divide-y divide-slate-200 [&_th]:border [&_th]:border-slate-200 [&_th]:bg-slate-50 [&_th]:px-3 [&_th]:py-2 [&_th]:font-semibold [&_th]:text-slate-700 [&_td]:border [&_td]:border-slate-200 [&_td]:px-3 [&_td]:py-2 [&_td]:text-slate-800">
          {children}
        </table>
      </div>
    );
  }

  return (
    <div className="not-prose my-4 rounded-xl border border-slate-200/90 bg-white shadow-sm overflow-hidden transition-all duration-200 hover:shadow-md">
      {/* 1. Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 px-4 py-3 bg-gradient-to-r from-slate-50 to-indigo-50/30 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
            <TableIcon className="w-4 h-4" />
          </div>
          <span className="text-xs font-semibold text-slate-800">
            {title || 'Bảng số liệu thống kê chi tiết'}
          </span>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-200/70 text-slate-600 font-medium">
            {filteredRows.length} bản ghi
          </span>
        </div>

        <div className="flex items-center gap-1.5 ml-auto">
          {/* Ô tìm kiếm nhanh */}
          {rows.length > 3 && (
            <div className="relative">
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setCurrentPage(1);
                }}
                placeholder="Lọc dòng..."
                className="w-28 sm:w-36 pl-7 pr-2 py-1 text-xs rounded-lg border border-slate-200 bg-white text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 transition"
              />
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2 top-1/2 -translate-y-1/2" />
            </div>
          )}

          {/* Nút Sao chép */}
          <button
            onClick={handleCopy}
            className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg border transition shadow-sm ${
              copied
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50 hover:text-slate-900'
            }`}
            title="Sao chép bảng để dán vào Excel"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Đã chép' : 'Sao chép'}</span>
          </button>

          {/* Nút Xuất CSV */}
          <button
            onClick={handleExportCsv}
            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 hover:text-slate-900 transition shadow-sm"
            title="Tải bảng dạng tệp CSV cho Excel"
          >
            <Download className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Xuất CSV</span>
          </button>
        </div>
      </div>

      {/* 2. Khung cuộn ngang bảng dữ liệu */}
      <div className="overflow-x-auto max-w-full">
        <table className="w-full text-left border-collapse text-[13px]">
          <thead>
            <tr className="bg-slate-100/80 border-b border-slate-200 text-slate-700 select-none">
              {columns.map((col) => {
                const isSorted = sortKey === col.key;
                return (
                  <th
                    key={col.key}
                    onClick={() => handleSort(col.key)}
                    className={`py-2.5 px-3.5 text-xs font-semibold uppercase tracking-wider cursor-pointer hover:bg-slate-200/70 transition-colors whitespace-nowrap ${
                      col.align === 'center' ? 'text-center' : col.align === 'right' ? 'text-right' : 'text-left'
                    }`}
                  >
                    <div
                      className={`inline-flex items-center gap-1.5 ${
                        col.align === 'center' ? 'justify-center' : col.align === 'right' ? 'justify-end' : 'justify-start'
                      }`}
                    >
                      <span>{col.label}</span>
                      {isSorted ? (
                        sortOrder === 'asc' ? (
                          <ArrowUp className="w-3.5 h-3.5 text-blue-600" />
                        ) : (
                          <ArrowDown className="w-3.5 h-3.5 text-blue-600" />
                        )
                      ) : (
                        <ArrowUpDown className="w-3 h-3 text-slate-400 opacity-60 hover:opacity-100" />
                      )}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {paginatedRows.length > 0 ? (
              paginatedRows.map((row, rIdx) => (
                <tr
                  key={`r-${rIdx}`}
                  className="odd:bg-white even:bg-slate-50/50 hover:bg-blue-50/40 transition-colors duration-150"
                >
                  {columns.map((col) => (
                    <td
                      key={`c-${col.key}`}
                      className={`py-2.5 px-3.5 whitespace-nowrap ${
                        col.align === 'center'
                          ? 'text-center'
                          : col.align === 'right'
                          ? 'text-right'
                          : 'text-left'
                      }`}
                    >
                      {renderCellContent(row[col.key], col)}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="text-center py-6 text-slate-400 text-xs italic">
                  Không tìm thấy dòng số liệu nào khớp với từ khóa tìm kiếm.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 3. Phân trang Chân trang (Footer Pagination) */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-2 bg-slate-50/70 border-t border-slate-200 text-xs text-slate-600">
          <div className="text-[11px] text-slate-500 font-medium">
            Hiển thị {(currentPage - 1) * PAGE_SIZE + 1} -{' '}
            {Math.min(currentPage * PAGE_SIZE, sortedRows.length)} trong số {sortedRows.length} dòng
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="p-1 rounded-md border border-slate-200 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
              title="Trang trước"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 font-medium text-slate-700">
              {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="p-1 rounded-md border border-slate-200 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
              title="Trang sau"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
