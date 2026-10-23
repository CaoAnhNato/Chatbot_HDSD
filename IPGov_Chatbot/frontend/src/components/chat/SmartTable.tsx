'use client';

import React, { useState, useMemo, useRef, useLayoutEffect, useCallback, useEffect } from 'react';
import { TabularData, TableColumn, PinnedDrawerItem, TemporalScopeMeta } from '@/types/chat';
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Copy,
  Check,
  Download,
  Search,
  ChevronDown,
  Table as TableIcon,
  Pin,
  Clock,
  SlidersHorizontal,
  X,
  MessageSquarePlus,
  Layers,
  Filter,
} from 'lucide-react';

interface SmartTableProps {
  tabularData?: TabularData;
  children?: React.ReactNode;
  onSelectChip?: (chip: string) => void;
  onPinItem?: (item: PinnedDrawerItem) => void;
}

// Hàm bỏ dấu tiếng Việt phục vụ tìm kiếm không dấu (GP 1.3)
export function removeVietnameseTones(str: string): string {
  return String(str || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .trim();
}

// Hàm trích xuất text thuần từ cây React Nodes
export function extractTextFromReactNode(node: any): string {
  if (node === null || node === undefined || typeof node === 'boolean') return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(extractTextFromReactNode).join('');
  if (
    React.isValidElement(node) &&
    node.props &&
    (node.props as any).children !== undefined &&
    (node.props as any).children !== null
  ) {
    return extractTextFromReactNode((node.props as any).children);
  }
  return '';
}

// Phân tích thẻ <table> HTML/ReactNode do ReactMarkdown sinh ra
export function parseTableFromChildren(children: React.ReactNode): {
  columns: TableColumn[];
  rows: Record<string, any>[];
} {
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
          let hIdx = 0;
          React.Children.forEach(trChildren, (th) => {
            if (!React.isValidElement(th)) return;
            const text = extractTextFromReactNode(th).trim();
            const alignAttr = (th.props as any)?.align || 'left';
            const align =
              alignAttr === 'center' ? 'center' : alignAttr === 'right' ? 'right' : 'left';
            const isBadge = ['trạng thái', 'tình trạng', 'status', 'phê duyệt'].some((k) =>
              text.toLowerCase().includes(k)
            );
            const isNum = [
              'stt',
              'số lượng',
              'kinh phí',
              'tổng',
              'giá trị',
              'chênh lệch',
              'số chỉ tiêu',
            ].some((k) => text.toLowerCase().includes(k));
            columns.push({
              key: `col_${hIdx}`,
              label: text || `Cột ${hIdx + 1}`,
              align: isNum && !text.toLowerCase().includes('stt') ? 'right' : align,
              data_type: isBadge ? 'badge' : isNum ? 'number' : 'text',
            });
            hIdx++;
          });
        });
      }

      // Xử lý tbody
      if (typeName === 'tbody' || typeName.includes('tbody')) {
        const tbodyChildren = (child.props as any)?.children;
        React.Children.forEach(tbodyChildren, (tr) => {
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
          let hIdx = 0;
          React.Children.forEach(trChildren, (cell) => {
            if (!React.isValidElement(cell)) return;
            const text = extractTextFromReactNode(cell).trim();
            columns.push({
              key: `col_${hIdx}`,
              label: text || `Cột ${hIdx + 1}`,
              align: 'left',
              data_type: 'text',
            });
            hIdx++;
          });
        } else {
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

export function normalizeHeaderLabel(label: string): string {
  return String(label || '')
    .toLowerCase()
    .replace(/[`*_~]/g, '')
    .replace(/\s*\([^)]*\)\s*/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function doHeadersMatch(mdCols: TableColumn[], tdCols: TableColumn[]): boolean {
  if (mdCols.length === 0 || mdCols.length !== tdCols.length) return false;
  let matchCount = 0;
  for (let i = 0; i < mdCols.length; i++) {
    const mdNorm = normalizeHeaderLabel(mdCols[i].label);
    const tdNorm = normalizeHeaderLabel(tdCols[i].label);
    const tdKey = String(tdCols[i].key || '').toLowerCase().trim();
    if (
      mdNorm === tdNorm ||
      mdNorm === tdKey ||
      (mdNorm.length >= 4 && tdNorm.length >= 4 && (mdNorm.includes(tdNorm) || tdNorm.includes(mdNorm)))
    ) {
      matchCount++;
    } else if (
      (mdNorm.includes('chỉ tiêu') &&
        tdNorm.includes('chỉ tiêu') &&
        mdNorm.includes('số liệu') &&
        tdNorm.includes('số liệu')) ||
      (mdNorm.includes('chỉ tiêu gốc') && tdNorm.includes('chỉ tiêu gốc'))
    ) {
      matchCount++;
    }
  }
  return matchCount === mdCols.length;
}

export function doFirstRowMatch(
  mdRows: Record<string, any>[],
  mdCols: TableColumn[],
  tdRows: Record<string, any>[],
  tdCols: TableColumn[]
): boolean {
  if (mdRows.length === 0 || tdRows.length === 0) return true;
  const mdRow0 = mdRows[0] || {};
  const tdRow0 = tdRows[0] || {};
  let nonSttCount = 0;
  let matchedCount = 0;

  for (let i = 0; i < mdCols.length; i++) {
    const labelNorm = normalizeHeaderLabel(mdCols[i].label);
    const keyNorm = String(tdCols[i]?.key || '').toLowerCase().trim();
    if (labelNorm === 'stt' || keyNorm === 'stt') continue;
    nonSttCount++;

    const mdVal = cleanDisplayString(mdRow0[mdCols[i].key]).toLowerCase();
    const tdVal = cleanDisplayString(tdRow0[tdCols[i]?.key ?? mdCols[i].key]).toLowerCase();
    if (
      mdVal === tdVal ||
      (mdVal.length > 0 && tdVal.length > 0 && (mdVal.includes(tdVal) || tdVal.includes(mdVal)))
    ) {
      matchedCount++;
    }
  }

  if (nonSttCount === 0) return true;
  return matchedCount >= Math.ceil(nonSttCount / 2);
}

export function resolveSmartTableData(
  tabularData?: TabularData,
  children?: React.ReactNode
): {
  columns: TableColumn[];
  rows: Record<string, any>[];
  title?: string;
  treeModal: Record<string, any>;
  isPrimaryTable: boolean;
} {
  const parsed = parseTableFromChildren(children);
  const mdColumns = parsed.columns;
  const mdRows = parsed.rows;

  const tdColumns: TableColumn[] = Array.isArray(tabularData?.columns)
    ? tabularData!.columns
    : Array.isArray(tabularData) && (tabularData as any[]).length > 0 && typeof (tabularData as any[])[0] === 'object'
    ? Object.keys((tabularData as any[])[0]).map((k) => ({
        key: k,
        label: k,
        align: 'left',
        data_type: 'text',
      }))
    : [];

  const tdRows: Record<string, any>[] = Array.isArray(tabularData?.rows)
    ? tabularData!.rows
    : Array.isArray(tabularData)
    ? (tabularData as any[])
    : [];

  const hasTabularData = tdColumns.length > 0;
  const rawTreeModal =
    (tabularData as any)?.tree_modal || (tabularData as any)?.trees_by_root_id || {};

  // (a) Không có mdRows được phân tích từ children -> dùng trực tiếp tabularData nếu có
  if (mdRows.length === 0 && mdColumns.length === 0 && hasTabularData) {
    return {
      columns: tdColumns,
      rows: tdRows,
      title: (tabularData as any)?.title,
      treeModal: rawTreeModal,
      isPrimaryTable: true,
    };
  }

  // (b) Bảng Markdown có số cột, tên header, số dòng và dòng đầu khớp với tabularData -> làm giàu dữ liệu từ tabularData
  if (
    hasTabularData &&
    mdColumns.length === tdColumns.length &&
    mdRows.length === tdRows.length &&
    doHeadersMatch(mdColumns, tdColumns) &&
    doFirstRowMatch(mdRows, mdColumns, tdRows, tdColumns)
  ) {
    const enrichedColumns: TableColumn[] = mdColumns.map((mdCol, idx) => {
      const tdCol = tdColumns[idx];
      return {
        key: tdCol?.key || mdCol.key,
        label: mdCol.label || tdCol?.label || `Cột ${idx + 1}`,
        align: tdCol?.align || mdCol.align,
        data_type: tdCol?.data_type || mdCol.data_type,
      };
    });

    const enrichedRows: Record<string, any>[] = mdRows.map((mdRow, rIdx) => {
      const tdRow = tdRows[rIdx] || {};
      const merged: Record<string, any> = { ...tdRow, ...mdRow };
      mdColumns.forEach((mdCol, cIdx) => {
        const targetKey = tdColumns[cIdx]?.key || mdCol.key;
        if (mdRow[mdCol.key] !== undefined && mdRow[mdCol.key] !== '') {
          merged[targetKey] = mdRow[mdCol.key];
        } else if (tdRow[targetKey] !== undefined) {
          merged[targetKey] = tdRow[targetKey];
        }
      });
      return merged;
    });

    return {
      columns: enrichedColumns,
      rows: enrichedRows,
      title: (tabularData as any)?.title,
      treeModal: rawTreeModal,
      isPrimaryTable: true,
    };
  }

  // Các bảng Markdown thứ 2, thứ 3 (khác header hoặc khác số dòng) render đúng mdColumns và mdRows của chính nó
  return {
    columns: mdColumns,
    rows: mdRows,
    title: undefined,
    treeModal: {},
    isPrimaryTable: false,
  };
}

// Render Badge trạng thái tự động hoặc format văn bản
function renderCellContent(value: any, column: TableColumn) {
  if (value === null || value === undefined) return '-';
  const rawStr = String(value).trim();
  const clean = rawStr.replace(/^\*\*|\*\*$/g, '').replace(/^`|`$/g, '').trim();
  const lower = clean.toLowerCase();

  if (
    ['draft', 'bản nháp', 'dự thảo', 'đang thực hiện', 'cần rà soát'].some(
      (k) => lower === k || lower.includes(`(${k})`) || lower.startsWith(k)
    )
  ) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 shadow-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mr-1.5"></span>
        {clean}
      </span>
    );
  }

  if (
    ['rejected', 'bị từ chối', 'thất bại', 'inactive', 'tạm dừng', 'chưa kích hoạt'].some(
      (k) => lower === k || lower.includes(`(${k})`) || lower.startsWith(k)
    )
  ) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200 shadow-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mr-1.5"></span>
        {clean}
      </span>
    );
  }

  if (
    ['pending', 'chờ phê duyệt', 'chờ duyệt'].some(
      (k) => lower === k || lower.includes(`(${k})`) || lower.startsWith(k)
    )
  ) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200 shadow-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mr-1.5"></span>
        {clean}
      </span>
    );
  }

  if (
    column.data_type === 'badge' ||
    ['approved', 'đã phê duyệt', 'hoàn thành', 'thành công', 'active', 'đang kích hoạt'].some(
      (k) => lower === k || lower.includes(`(${k})`) || lower.startsWith(k)
    )
  ) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse"></span>
        {clean}
      </span>
    );
  }

  if (rawStr.startsWith('**') && rawStr.endsWith('**')) {
    return <span className="font-semibold text-slate-900">{clean}</span>;
  }

  if (column.data_type === 'number') {
    return <span className="font-mono font-medium text-slate-800">{clean}</span>;
  }

  return <span className="text-slate-700">{clean}</span>;
}

interface NormalizedTreeNode {
  uid: string;
  parentId: string | null;
  parentName: string;
  level: 1 | 2 | 3;
  name: string;
  value: any;
  report_date: string;
  office_name: string;
  mission_name: string;
  children: NormalizedTreeNode[];
}

function cleanDisplayString(val: any, fallback = ''): string {
  if (val === null || val === undefined) return fallback;
  return String(val).replace(/^\*\*|\*\*$/g, '').replace(/^`|`$/g, '').trim() || fallback;
}

function hasValidMetricValue(val: any): boolean {
  if (val === null || val === undefined) return false;
  const s = cleanDisplayString(val).toLowerCase();
  if (
    s === '' ||
    s === '-' ||
    s === 'none' ||
    s === 'null' ||
    s.includes('chưa có số liệu') ||
    s.includes('không có số liệu')
  ) {
    return false;
  }
  return true;
}

function highlightMatchText(text: string, rawSearchTerm: string): React.ReactNode {
  const cleanTerm = removeVietnameseTones(rawSearchTerm);
  if (!cleanTerm || !text) return text;
  const normText = text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase();
  const matchIdx = normText.indexOf(cleanTerm);
  if (matchIdx < 0) return text;
  const before = text.slice(0, matchIdx);
  const match = text.slice(matchIdx, matchIdx + cleanTerm.length);
  const after = text.slice(matchIdx + cleanTerm.length);
  return (
    <>
      {before}
      <mark
        data-testid="tree-search-highlight"
        className="bg-amber-200/90 text-slate-900 rounded px-0.5 font-extrabold"
      >
        {match}
      </mark>
      {after}
    </>
  );
}

function parseNumericForSparkbar(val: any): number {
  if (!hasValidMetricValue(val)) return 0;
  const cleaned = cleanDisplayString(val).replace(/\s*\([^)]*\)\s*/g, '').trim();
  if (/^[+-]?\d{1,3}(\.\d{3})+(,\d+)?$/.test(cleaned)) {
    return parseFloat(cleaned.replace(/\./g, '').replace(',', '.')) || 0;
  }
  return parseFloat(cleaned.replace(/,/g, '')) || 0;
}

function normalizeTreeData(rawRoot: any): NormalizedTreeNode {
  const rootName = cleanDisplayString(rawRoot?.name, 'Nhóm chỉ tiêu Cấp 1');
  const rootUid = String(rawRoot?.id || rawRoot?.code || `l1-${rootName || 'root'}`);
  const rootReportDate = cleanDisplayString(rawRoot?.report_date, '31/03/2026');
  const rawL2: any[] = Array.isArray(rawRoot?.children) ? rawRoot.children : [];

  const l2Nodes: NormalizedTreeNode[] = rawL2.map((c2: any, idx2: number) => {
    const l2Uid = String(c2?.id || c2?.code || `${rootUid}-l2-${idx2}`);
    const l2Name = cleanDisplayString(c2?.name, 'Chỉ tiêu Cấp 2');
    const l2Date = cleanDisplayString(c2?.report_date || rootReportDate, '31/03/2026');
    const rawL3: any[] = Array.isArray(c2?.children) ? c2.children : [];
    const l3Nodes: NormalizedTreeNode[] = rawL3.map((c3: any, idx3: number) => ({
      uid: String(c3?.id || c3?.code || `${l2Uid}-l3-${idx3}`),
      parentId: l2Uid,
      parentName: l2Name,
      level: 3,
      name: cleanDisplayString(c3?.name, 'Chỉ tiêu Cấp 3'),
      value: c3?.value,
      report_date: cleanDisplayString(c3?.report_date || l2Date, '31/03/2026'),
      office_name: cleanDisplayString(
        c3?.office_name || c2?.office_name || rawRoot?.office_name,
        'Cấp tỉnh'
      ),
      mission_name: cleanDisplayString(
        c3?.mission_name || c2?.mission_name || rawRoot?.mission_name,
        ''
      ),
      children: [],
    }));
    return {
      uid: l2Uid,
      parentId: rootUid,
      parentName: rootName,
      level: 2,
      name: l2Name,
      value: c2?.value,
      report_date: l2Date,
      office_name: cleanDisplayString(c2?.office_name || rawRoot?.office_name, 'Cấp tỉnh'),
      mission_name: cleanDisplayString(c2?.mission_name || rawRoot?.mission_name, ''),
      children: l3Nodes,
    };
  });

  return {
    uid: rootUid,
    parentId: null,
    parentName: 'Danh mục gốc',
    level: 1,
    name: rootName,
    value: rawRoot?.value,
    report_date: rootReportDate,
    office_name: cleanDisplayString(rawRoot?.office_name, 'Cấp tỉnh'),
    mission_name: cleanDisplayString(rawRoot?.mission_name, ''),
    children: l2Nodes,
  };
}

const InteractiveCriteriaTreeCanvas: React.FC<{
  rawRoot: any;
  globalExpandSignal?: number;
  treeSearchTerm?: string;
  treeStatusFilter?: 'all' | 'has_value' | 'no_value';
  viewMode?: 'tree' | 'compact_table';
  temporalScope?: TemporalScopeMeta;
  onSelectChip?: (chip: string) => void;
  onClose?: () => void;
  onResetFilter?: () => void;
}> = ({
  rawRoot,
  globalExpandSignal,
  treeSearchTerm = '',
  treeStatusFilter = 'all',
  viewMode = 'tree',
  temporalScope,
  onSelectChip,
  onClose,
  onResetFilter,
}) => {
  const tree = useMemo(() => normalizeTreeData(rawRoot), [rawRoot]);

  // Tổng số nút con (Cấp 2 + Cấp 3) để quyết định auto-collapse Level 3 khi > 7 (GP 1.3)
  const totalDescendantCount = useMemo(() => {
    let count = tree.children.length;
    tree.children.forEach((l2) => {
      count += l2.children.length;
    });
    return count;
  }, [tree]);

  const computeInitialCollapsed = useCallback(
    (rootNode: NormalizedTreeNode, totalDesc: number): Record<string, boolean> => {
      if (totalDesc > 7) {
        const init: Record<string, boolean> = {};
        rootNode.children.forEach((l2) => {
          if (l2.children.length > 0) {
            init[l2.uid] = true;
          }
        });
        return init;
      }
      return {};
    },
    []
  );

  const [collapsedIds, setCollapsedIds] = useState<Record<string, boolean>>(() =>
    computeInitialCollapsed(tree, totalDescendantCount)
  );
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Tier 1 Multi-Metric Comparison Tray (tối đa 4 chỉ tiêu con, FIFO khi chọn thẻ thứ 5)
  const [comparedNodes, setComparedNodes] = useState<NormalizedTreeNode[]>([]);
  const [compareToast, setCompareToast] = useState<string | null>(null);

  useEffect(() => {
    setCollapsedIds(computeInitialCollapsed(tree, totalDescendantCount));
  }, [tree, totalDescendantCount, computeInitialCollapsed]);

  useEffect(() => {
    if (globalExpandSignal !== undefined && globalExpandSignal > 0) {
      setCollapsedIds({});
    }
  }, [globalExpandSignal]);

  // Khi người dùng gõ tìm kiếm hoặc lọc trạng thái -> tự động bung các nhánh Cấp 2 có con khớp
  const normalizedSearch = useMemo(
    () => removeVietnameseTones(treeSearchTerm),
    [treeSearchTerm]
  );

  const matchesNodeFilter = useCallback(
    (node: NormalizedTreeNode): boolean => {
      const hasVal = hasValidMetricValue(node.value);
      if (treeStatusFilter === 'has_value' && !hasVal) return false;
      if (treeStatusFilter === 'no_value' && hasVal) return false;
      if (!normalizedSearch) return true;
      const nodeNorm = removeVietnameseTones(node.name);
      return nodeNorm.includes(normalizedSearch);
    },
    [treeStatusFilter, normalizedSearch]
  );

  // Ancestor-Preserving Filter: Giữ nhánh Cấp 2 nếu bản thân Cấp 2 khớp HOẶC có ít nhất 1 con Cấp 3 khớp
  const filteredTree = useMemo(() => {
    const isFiltering = Boolean(normalizedSearch) || treeStatusFilter !== 'all';
    if (!isFiltering) return tree;

    const nextL2: NormalizedTreeNode[] = [];
    for (const l2 of tree.children) {
      const matchingL3 = l2.children.filter(matchesNodeFilter);
      const selfMatches = matchesNodeFilter(l2);
      if (selfMatches || matchingL3.length > 0) {
        nextL2.push({
          ...l2,
          children: matchingL3.length > 0 ? matchingL3 : selfMatches ? l2.children : [],
        });
      }
    }
    return {
      ...tree,
      children: nextL2,
    };
  }, [tree, normalizedSearch, treeStatusFilter, matchesNodeFilter]);

  const isFilteringActive = Boolean(normalizedSearch) || treeStatusFilter !== 'all';

  const selectedNode = useMemo(() => {
    if (!selectedId) return null;
    if (tree.uid === selectedId) return tree;
    for (const l2 of tree.children) {
      if (l2.uid === selectedId) return l2;
      for (const l3 of l2.children) {
        if (l3.uid === selectedId) return l3;
      }
    }
    return null;
  }, [selectedId, tree]);

  const toggleCompareNode = useCallback((node: NormalizedTreeNode, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setComparedNodes((prev) => {
      const exists = prev.some((n) => n.uid === node.uid);
      if (exists) {
        return prev.filter((n) => n.uid !== node.uid);
      }
      if (prev.length >= 4) {
        setCompareToast('Tối đa 4 chỉ tiêu đối chiếu cùng lúc (đã tự động thay thế thẻ cũ nhất).');
        setTimeout(() => setCompareToast(null), 3000);
        return [...prev.slice(1), node];
      }
      return [...prev, node];
    });
  }, []);

  const handleNodeClick = useCallback(
    (node: NormalizedTreeNode) => {
      setSelectedId((prev) => (prev === node.uid ? null : node.uid));
      if (node.level > 1) {
        toggleCompareNode(node);
      }
    },
    [toggleCompareNode]
  );

  const [edges, setEdges] = useState<
    Array<{
      id: string;
      from: string;
      to: string;
      d: string;
      startX: number;
      startY: number;
      endX: number;
      endY: number;
    }>
  >([]);
  const [svgSize, setSvgSize] = useState({ width: 960, height: 420 });

  const containerRef = useRef<HTMLDivElement | null>(null);
  const nodeRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const subgridRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const toggleCollapse = useCallback((uid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCollapsedIds((prev) => ({ ...prev, [uid]: !prev[uid] }));
  }, []);

  const visibleL2 = useMemo(() => {
    if (!isFilteringActive && collapsedIds[filteredTree.uid]) return [];
    return filteredTree.children;
  }, [filteredTree, collapsedIds, isFilteringActive]);

  const visibleL3 = useMemo(() => {
    if (!isFilteringActive && collapsedIds[filteredTree.uid]) return [];
    const list: NormalizedTreeNode[] = [];
    filteredTree.children.forEach((l2) => {
      const isL2Collapsed = !isFilteringActive && collapsedIds[l2.uid];
      if (!isL2Collapsed && l2.children.length > 0) {
        list.push(...l2.children);
      }
    });
    return list;
  }, [filteredTree, collapsedIds, isFilteringActive]);

  const hasAnyL3InTree = useMemo(
    () => filteredTree.children.some((l2) => l2.children.length > 0),
    [filteredTree]
  );

  const activeFocusId = hoveredId || selectedId;

  const relatedIds = useMemo(() => {
    if (!activeFocusId) return new Set<string>();
    const set = new Set<string>([activeFocusId]);

    const parentMap: Record<string, string | null> = { [tree.uid]: null };
    const childrenMap: Record<string, string[]> = { [tree.uid]: tree.children.map((c) => c.uid) };
    tree.children.forEach((l2) => {
      parentMap[l2.uid] = tree.uid;
      childrenMap[l2.uid] = l2.children.map((c) => c.uid);
      l2.children.forEach((l3) => {
        parentMap[l3.uid] = l2.uid;
        childrenMap[l3.uid] = [];
      });
    });

    let curr: string | null = activeFocusId;
    while (curr && parentMap[curr]) {
      const p: string = parentMap[curr]!;
      set.add(p);
      curr = p;
    }

    const addDesc = (id: string) => {
      (childrenMap[id] || []).forEach((cid) => {
        set.add(cid);
        addDesc(cid);
      });
    };
    addDesc(activeFocusId);

    return set;
  }, [activeFocusId, tree]);

  const calculateEdges = useCallback(() => {
    if (!containerRef.current || viewMode !== 'tree') return;
    const containerEl = containerRef.current;
    const containerRect = containerEl.getBoundingClientRect();
    if (containerRect.width === 0 && containerRect.height === 0) return;

    setSvgSize({
      width: Math.max(containerEl.scrollWidth, containerRect.width),
      height: Math.max(containerEl.scrollHeight, containerRect.height),
    });

    const newEdges: typeof edges = [];
    const connectElements = (
      fromId: string,
      toId: string,
      pEl: HTMLElement | null,
      cEl: HTMLElement | null
    ) => {
      if (!pEl || !cEl) return;
      const pRect = pEl.getBoundingClientRect();
      const cRect = cEl.getBoundingClientRect();
      if (pRect.width === 0 || cRect.width === 0) return;

      const startX = pRect.right - containerRect.left + containerEl.scrollLeft;
      const startY = pRect.top + pRect.height / 2 - containerRect.top + containerEl.scrollTop;
      const endX = cRect.left - containerRect.left + containerEl.scrollLeft - 6;
      const endY = cRect.top + cRect.height / 2 - containerRect.top + containerEl.scrollTop;
      const controlOffset = Math.max(28, (endX - startX) * 0.5);
      const d = `M ${startX} ${startY} C ${startX + controlOffset} ${startY}, ${endX - controlOffset} ${endY}, ${endX} ${endY}`;

      newEdges.push({
        id: `${fromId}->${toId}`,
        from: fromId,
        to: toId,
        d,
        startX,
        startY,
        endX,
        endY,
      });
    };

    if (isFilteringActive || !collapsedIds[filteredTree.uid]) {
      filteredTree.children.forEach((l2) => {
        connectElements(
          filteredTree.uid,
          l2.uid,
          nodeRefs.current[filteredTree.uid],
          nodeRefs.current[l2.uid]
        );
        const isL2Collapsed = !isFilteringActive && collapsedIds[l2.uid];
        if (!isL2Collapsed && l2.children.length > 0) {
          // GP 1.3: Nối 1 đường cong Cubic Bezier duy nhất từ Cấp 2 sang Khung 2-Column Sub-Grid Cấp 3 (hoặc từng nút)
          const subgridEl = subgridRefs.current[l2.uid];
          if (subgridEl && l2.children.length > 1) {
            connectElements(l2.uid, l2.children[0].uid, nodeRefs.current[l2.uid], subgridEl);
          } else {
            l2.children.forEach((l3) => {
              connectElements(l2.uid, l3.uid, nodeRefs.current[l2.uid], nodeRefs.current[l3.uid]);
            });
          }
        }
      });
    }

    setEdges(newEdges);
  }, [filteredTree, collapsedIds, isFilteringActive, viewMode]);

  useLayoutEffect(() => {
    calculateEdges();
    const t1 = setTimeout(calculateEdges, 50);
    const t2 = setTimeout(calculateEdges, 180);
    const ro =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(() => calculateEdges())
        : null;
    if (ro && containerRef.current) {
      ro.observe(containerRef.current);
    }
    window.addEventListener('resize', calculateEdges);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      if (ro) ro.disconnect();
      window.removeEventListener('resize', calculateEdges);
    };
  }, [calculateEdges, visibleL2.length, visibleL3.length, viewMode]);

  const querySuffix = temporalScope?.query_suffix || 'năm 2026';

  const renderNodeCard = (node: NormalizedTreeNode) => {
    const hasVal = hasValidMetricValue(node.value);
    const hasChildren = node.children.length > 0;
    const isCollapsed = !isFilteringActive && Boolean(collapsedIds[node.uid]);
    const isSelected = selectedId === node.uid;
    const isCompared = comparedNodes.some((n) => n.uid === node.uid);
    const isHighlighted = activeFocusId ? relatedIds.has(node.uid) : false;
    const isDimmed = activeFocusId ? !relatedIds.has(node.uid) : false;

    return (
      <div
        key={node.uid}
        data-testid={`tree-node-${node.level}`}
        ref={(el) => {
          nodeRefs.current[node.uid] = el;
        }}
        onClick={() => handleNodeClick(node)}
        onMouseEnter={() => setHoveredId(node.uid)}
        onMouseLeave={() => setHoveredId(null)}
        className={`relative rounded-xl bg-white p-3.5 transition-all duration-200 cursor-pointer select-none border ${
          isSelected || isCompared
            ? 'border-indigo-600 ring-2 ring-indigo-500/20 shadow-md'
            : isHighlighted
            ? 'border-indigo-400 shadow-sm bg-indigo-50/15'
            : 'border-slate-200 hover:border-slate-300 shadow-2xs'
        } ${isDimmed ? 'opacity-40' : 'opacity-100'}`}
      >
        {/* Dòng 1: Cấp độ + Giá trị hoặc trạng thái nhóm + Nút so sánh / đóng mở nhánh */}
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <div className="flex items-center gap-1.5">
            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono text-[10px] font-semibold">
              Cấp {node.level}
            </span>
            {node.level > 1 && (
              <button
                type="button"
                data-testid={`tree-compare-toggle-${node.uid}`}
                onClick={(e) => toggleCompareNode(node, e)}
                title="Chọn/Bỏ chọn vào khay đối chiếu đa chỉ tiêu (Tier 1)"
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold border transition ${
                  isCompared
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-indigo-50 hover:text-indigo-700'
                }`}
              >
                {isCompared ? '✓ Đang đối chiếu' : '+ Đối chiếu'}
              </button>
            )}
          </div>

          <div className="flex items-center gap-1.5">
            {hasVal ? (
              <span className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold text-xs">
                Số lượng: {String(node.value)}
              </span>
            ) : hasChildren ? (
              <span className="px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200 text-[11px] font-semibold">
                Nhóm cha ({node.children.length} chỉ tiêu con)
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 border border-amber-200 text-[11px]">
                Chưa có số liệu phê duyệt (-)
              </span>
            )}

            {hasChildren && (
              <button
                type="button"
                data-testid={`toggle-branch-${node.level}`}
                onClick={(e) => toggleCollapse(node.uid, e)}
                title={isCollapsed ? 'Mở rộng nhánh con' : 'Thu gọn nhánh con'}
                className={`h-6 px-1.5 rounded-md border text-[10px] font-bold flex items-center justify-center transition ${
                  isCollapsed
                    ? 'bg-indigo-600 text-white border-indigo-600 hover:bg-indigo-500'
                    : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                }`}
              >
                {isCollapsed ? `+${node.children.length}` : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>
        </div>

        {/* Dòng 2: Tên chỉ tiêu (kèm tô sáng <mark> khi tìm kiếm) */}
        <div className="text-xs font-bold text-slate-800 leading-snug">
          {highlightMatchText(node.name, treeSearchTerm)}
        </div>

        {/* Dòng 3: Đơn vị thực hiện */}
        <div className="text-[11px] text-slate-500 mt-1">
          Đơn vị: <span className="font-medium text-slate-700">{node.office_name}</span>
        </div>

        {/* Nút 1-Click Drill-Down: Tra cứu số liệu chi tiết của chỉ tiêu lá */}
        {!hasChildren && node.level > 1 && (
          <div className="mt-2 pt-2 border-t border-slate-100 flex items-center justify-end">
            <button
              type="button"
              data-testid={`drilldown-leaf-${node.level}`}
              title={`Tra cứu số liệu chỉ tiêu ${node.name} thuộc nhóm ${tree.name}`}
              aria-label={`Tra cứu số liệu chỉ tiêu ${node.name} thuộc nhóm ${tree.name}`}
              onClick={(e) => {
                e.stopPropagation();
                onClose?.();
                onSelectChip?.(
                  `Cho tôi biết số liệu chỉ tiêu ${node.name} thuộc nhóm ${tree.name} ${querySuffix}?`
                );
              }}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-600 text-indigo-700 hover:text-white border border-indigo-200 hover:border-indigo-600 text-[11px] font-semibold transition-all cursor-pointer shadow-2xs"
            >
              <span>🔍 Tra cứu số liệu</span>
            </button>
          </div>
        )}
      </div>
    );
  };

  // Max value in comparedNodes for Sparkbar percentage calculation
  const maxCompareNum = useMemo(() => {
    const nums = comparedNodes.map((n) => Math.abs(parseNumericForSparkbar(n.value)));
    return Math.max(...nums, 1);
  }, [comparedNodes]);

  return (
    <div
      ref={containerRef}
      className="relative rounded-2xl bg-white border border-slate-200 p-5 overflow-x-auto"
    >
      {/* Tiêu đề nhánh gốc tối giản */}
      <div className="flex items-center justify-between gap-2 mb-4 pb-2.5 border-b border-slate-100">
        <div className="text-xs font-bold text-indigo-700">
          Nhánh gốc Cấp 1: {tree.name} {tree.mission_name ? `(${tree.mission_name})` : ''}
        </div>
        {Object.values(collapsedIds).some(Boolean) && !isFilteringActive && (
          <button
            type="button"
            onClick={() => setCollapsedIds({})}
            className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-700 px-2 py-0.5 rounded bg-indigo-50 border border-indigo-200 transition"
          >
            Mở rộng lại các nhánh
          </button>
        )}
      </div>

      {/* Chế độ hiển thị 1: Bảng thu gọn phân cấp (Compact Hierarchical Table View) */}
      {viewMode === 'compact_table' ? (
        <div data-testid="tree-compact-table-view" className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-left border-collapse text-xs">
            <thead className="bg-slate-100 border-b border-slate-200 text-slate-700">
              <tr>
                <th className="py-2 px-3 font-bold">Cấp bậc</th>
                <th className="py-2 px-3 font-bold">Tên chỉ tiêu phân cấp</th>
                <th className="py-2 px-3 font-bold">Nhóm cha</th>
                <th className="py-2 px-3 font-bold text-right">Số liệu phê duyệt</th>
                <th className="py-2 px-3 font-bold">Kỳ báo cáo</th>
                <th className="py-2 px-3 font-bold">Đơn vị thực hiện</th>
                <th className="py-2 px-3 font-bold text-center">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredTree.children.map((l2) => (
                <React.Fragment key={l2.uid}>
                  <tr className="bg-indigo-50/30 hover:bg-indigo-50/70">
                    <td className="py-2 px-3 font-mono font-bold text-indigo-700">Cấp 2</td>
                    <td className="py-2 px-3 font-bold text-slate-900">
                      {highlightMatchText(l2.name, treeSearchTerm)}
                    </td>
                    <td className="py-2 px-3 text-slate-600">{l2.parentName}</td>
                    <td className="py-2 px-3 text-right font-mono font-bold text-emerald-700">
                      {hasValidMetricValue(l2.value) ? String(l2.value) : '-'}
                    </td>
                    <td className="py-2 px-3 text-slate-600">{l2.report_date}</td>
                    <td className="py-2 px-3 text-slate-700">{l2.office_name}</td>
                    <td className="py-2 px-3 text-center">
                      <button
                        type="button"
                        onClick={() => toggleCompareNode(l2)}
                        className="px-2 py-0.5 rounded bg-white border border-indigo-200 text-indigo-700 text-[11px] font-semibold hover:bg-indigo-600 hover:text-white transition"
                      >
                        {comparedNodes.some((n) => n.uid === l2.uid) ? '✓ Đã chọn' : '+ Đối chiếu'}
                      </button>
                    </td>
                  </tr>
                  {l2.children.map((l3) => (
                    <tr key={l3.uid} className="hover:bg-slate-50">
                      <td className="py-1.5 px-3 pl-6 font-mono text-slate-500">↳ Cấp 3</td>
                      <td className="py-1.5 px-3 pl-6 text-slate-800">
                        {highlightMatchText(l3.name, treeSearchTerm)}
                      </td>
                      <td className="py-1.5 px-3 text-slate-500">{l3.parentName}</td>
                      <td className="py-1.5 px-3 text-right font-mono font-bold text-emerald-700">
                        {hasValidMetricValue(l3.value) ? String(l3.value) : '-'}
                      </td>
                      <td className="py-1.5 px-3 text-slate-600">{l3.report_date}</td>
                      <td className="py-1.5 px-3 text-slate-700">{l3.office_name}</td>
                      <td className="py-1.5 px-3 text-center">
                        <button
                          type="button"
                          onClick={() => toggleCompareNode(l3)}
                          className="px-2 py-0.5 rounded bg-white border border-indigo-200 text-indigo-700 text-[11px] font-semibold hover:bg-indigo-600 hover:text-white transition"
                        >
                          {comparedNodes.some((n) => n.uid === l3.uid) ? '✓ Đã chọn' : '+ Đối chiếu'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <>
          {/* Tầng SVG vẽ đường cong Cubic Bezier nối Cạnh Phải (Cha) -> Cạnh Trái (Con) */}
          <svg
            width={svgSize.width}
            height={svgSize.height}
            className="absolute inset-0 pointer-events-none z-0"
            style={{ overflow: 'visible' }}
          >
            <defs>
              <marker
                id={`arrow-default-${tree.uid}`}
                markerWidth="8"
                markerHeight="8"
                refX="6"
                refY="4"
                orient="auto"
              >
                <path d="M 0 1 L 7 4 L 0 7 z" fill="#94a3b8" />
              </marker>
              <marker
                id={`arrow-active-${tree.uid}`}
                markerWidth="8"
                markerHeight="8"
                refX="6"
                refY="4"
                orient="auto"
              >
                <path d="M 0 1 L 7 4 L 0 7 z" fill="#4f46e5" />
              </marker>
            </defs>

            {edges.map((edge) => {
              const isEdgeActive =
                activeFocusId !== null &&
                relatedIds.has(edge.from) &&
                relatedIds.has(edge.to);
              const isEdgeDimmed = activeFocusId !== null && !isEdgeActive;

              return (
                <g
                  key={edge.id}
                  className="transition-opacity duration-200"
                  style={{ opacity: isEdgeDimmed ? 0.2 : 1 }}
                >
                  <path
                    d={edge.d}
                    fill="none"
                    stroke={isEdgeActive ? '#4f46e5' : '#cbd5e1'}
                    strokeWidth={isEdgeActive ? 2.4 : 1.6}
                    markerEnd={`url(#${isEdgeActive ? `arrow-active-${tree.uid}` : `arrow-default-${tree.uid}`})`}
                  />
                  <circle
                    cx={edge.startX}
                    cy={edge.startY}
                    r={3}
                    fill={isEdgeActive ? '#4f46e5' : '#94a3b8'}
                  />
                </g>
              );
            })}
          </svg>

          {/* Hàng tiêu đề 3 cột cố định ngay đầu khung nhìn */}
          <div
            className={`relative z-10 grid items-center gap-x-12 mb-3 ${
              hasAnyL3InTree
                ? 'grid-cols-[minmax(240px,270px)_minmax(250px,290px)_minmax(340px,1fr)]'
                : 'grid-cols-[minmax(260px,320px)_minmax(280px,360px)]'
            }`}
          >
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1">
              Cấp 1 • Nhóm chỉ tiêu gốc (Sticky)
            </div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1">
              Cấp 2 • Chỉ tiêu thành phần ({visibleL2.length})
            </div>
            {hasAnyL3InTree && (
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1">
                Cấp 3 • Chỉ tiêu chi tiết ({visibleL3.length} • Sub-Grid 2 cột)
              </div>
            )}
          </div>

          {/* Thân sơ đồ cây căn đỉnh (items-start), cột Cấp 1 có sticky top-4 (GP 1.3) */}
          <div
            className={`relative z-10 grid items-start gap-x-12 ${
              hasAnyL3InTree
                ? 'grid-cols-[minmax(240px,270px)_1fr]'
                : 'grid-cols-[minmax(260px,320px)_minmax(280px,360px)]'
            }`}
          >
            {/* CỘT 1: CẤP 1 (Sticky top-4 để không bao giờ trôi mất khi cuộn dọc) */}
            <div
              data-testid="tree-sticky-root-column"
              className="sticky top-4 self-start flex flex-col justify-start pt-1 z-10"
            >
              {renderNodeCard(filteredTree)}
            </div>

            {/* CỘT 2 & CỘT 3: Ghép theo từng cụm nhánh Cấp 2 -> Cấp 3 (2-Column Compact Sub-Grid) */}
            {visibleL2.length > 0 ? (
              <div className="flex flex-col space-y-4">
                {visibleL2.map((l2) => {
                  const isL2Collapsed = !isFilteringActive && Boolean(collapsedIds[l2.uid]);
                  const l3Children = isL2Collapsed ? [] : l2.children;
                  if (!hasAnyL3InTree) {
                    return <div key={`row-${l2.uid}`}>{renderNodeCard(l2)}</div>;
                  }
                  return (
                    <div
                      key={`row-${l2.uid}`}
                      className="grid grid-cols-[minmax(250px,290px)_minmax(340px,1fr)] items-center gap-x-12"
                    >
                      <div className="flex flex-col justify-center">
                        {renderNodeCard(l2)}
                      </div>
                      {l3Children.length > 0 ? (
                        <div
                          ref={(el) => {
                            subgridRefs.current[l2.uid] = el;
                          }}
                          data-testid={`tree-l3-subgrid-${l2.uid}`}
                          className={`grid gap-2.5 p-2.5 rounded-xl bg-slate-50/70 border border-slate-200/80 ${
                            l3Children.length > 1 ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'
                          }`}
                        >
                          {l3Children.map((l3) => renderNodeCard(l3))}
                        </div>
                      ) : (
                        <div className="text-[11px] text-slate-400 italic px-2 py-1">
                          {l2.children.length > 0
                            ? `Đã thu gọn ${l2.children.length} chỉ tiêu Cấp 3 (bấm +${l2.children.length} để bung)`
                            : 'Chỉ tiêu Cấp 2 độc lập'}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-xs text-slate-400 italic px-1 py-4 space-y-2">
                <div>
                  {isFilteringActive
                    ? 'Không có chỉ tiêu con nào khớp với bộ lọc hiện tại.'
                    : `Đã thu gọn nhánh Cấp 2 (bấm +${tree.children.length} ở thẻ Cấp 1 để mở)`}
                </div>
                {isFilteringActive && onResetFilter && (
                  <button
                    type="button"
                    data-testid="tree-empty-reset-button"
                    onClick={onResetFilter}
                    className="px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-semibold hover:bg-indigo-100 transition cursor-pointer not-italic"
                  >
                    Xóa bộ lọc
                  </button>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {/* Thanh Inspector Panel & Multi-Metric Comparison Tray (Tier 1 — GP 2.3: 0ms, 0 Backend Request) */}
      <div
        data-testid="tree-inspector-footer"
        className="sticky bottom-0 z-20 mt-4 pt-3 border-t border-slate-200 bg-slate-50/95 backdrop-blur-xs px-4 py-3 rounded-xl shadow-xs space-y-3"
      >
        {compareToast && (
          <div
            data-testid="tree-compare-toast"
            className="px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-[11px] font-medium"
          >
            {compareToast}
          </div>
        )}

        {/* Khay đối chiếu đa chỉ tiêu tại chỗ (1–4 thẻ 5 trường chuẩn + Sparkbar) */}
        {comparedNodes.length > 0 && (
          <div data-testid="tree-comparison-tray" className="space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded-md bg-indigo-600 text-white text-[11px] font-bold">
                  Khay Đối Chiếu Tại Chỗ ({comparedNodes.length}/4 chỉ tiêu • 0ms)
                </span>
                <span className="text-[11px] text-slate-500">
                  Chuẩn 5 trường: Tên chỉ tiêu • Nhóm cha • Giá trị • Kỳ báo cáo • Đơn vị
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  data-testid="push-comparison-to-chat"
                  onClick={() => {
                    const names = comparedNodes.map((n) => n.name).join(', ');
                    onClose?.();
                    onSelectChip?.(
                      `Cho tôi biết số liệu các chỉ tiêu ${names} thuộc nhóm ${tree.name} ${querySuffix}?`
                    );
                  }}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition cursor-pointer shadow-2xs"
                >
                  <MessageSquarePlus className="w-3.5 h-3.5" />
                  <span>💬 Đẩy bảng đối chiếu ra luồng Chat</span>
                </button>
                <button
                  type="button"
                  data-testid="clear-comparison-tray"
                  onClick={() => setComparedNodes([])}
                  className="px-2 py-1 rounded-lg bg-white hover:bg-rose-50 text-slate-600 hover:text-rose-600 border border-slate-200 text-[11px] font-semibold transition cursor-pointer"
                >
                  Xóa khay
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
              {comparedNodes.map((cNode, idx) => {
                const hasVal = hasValidMetricValue(cNode.value);
                const numVal = Math.abs(parseNumericForSparkbar(cNode.value));
                const barWidthPct = hasVal ? Math.max(8, Math.round((numVal / maxCompareNum) * 100)) : 0;

                return (
                  <div
                    key={cNode.uid}
                    data-testid={`comparison-card-${idx}`}
                    className="rounded-xl bg-white border border-indigo-200/90 p-3 shadow-2xs flex flex-col justify-between space-y-2"
                  >
                    <div className="space-y-1">
                      <div className="flex items-start justify-between gap-1.5">
                        <span className="px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 font-mono text-[10px] font-bold">
                          Cấp {cNode.level} • {cNode.parentName}
                        </span>
                        <button
                          type="button"
                          onClick={() => toggleCompareNode(cNode)}
                          className="text-slate-400 hover:text-rose-600"
                          title="Bỏ khỏi khay đối chiếu"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <div className="text-xs font-bold text-slate-900 leading-snug">
                        {cNode.name}
                      </div>
                    </div>

                    {/* Sparkbar & Value */}
                    <div className="space-y-1 pt-1 border-t border-slate-100">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-[10px] uppercase font-semibold text-slate-400">
                          Giá trị ({cNode.report_date}):
                        </span>
                        <span
                          className={`font-mono text-sm font-extrabold ${
                            hasVal ? 'text-emerald-700' : 'text-amber-600'
                          }`}
                        >
                          {hasVal ? String(cNode.value) : '- (Chưa có số liệu)'}
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          data-testid={`comparison-sparkbar-${idx}`}
                          className={`h-full rounded-full transition-all duration-300 ${
                            hasVal ? 'bg-indigo-600' : 'bg-amber-300'
                          }`}
                          style={{ width: `${barWidthPct}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-500 pt-0.5">
                        <span className="truncate" title={cNode.office_name}>
                          Đơn vị: <strong className="text-slate-700">{cNode.office_name}</strong>
                        </span>
                        {cNode.children.length === 0 && (
                          <button
                            type="button"
                            onClick={() => {
                              onClose?.();
                              onSelectChip?.(
                                `Cho tôi biết số liệu chỉ tiêu ${cNode.name} thuộc nhóm ${tree.name} ${querySuffix}?`
                              );
                            }}
                            className="text-indigo-600 hover:underline font-semibold shrink-0 ml-1"
                          >
                            🔍 Chi tiết
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Dòng Inspector đơn lẻ phía dưới */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          {selectedNode ? (
            <>
              <div className="text-xs text-slate-700 flex flex-wrap items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 font-mono text-[11px] font-semibold">
                  Cấp {selectedNode.level}
                </span>
                <span className="font-bold text-slate-900">{selectedNode.name}</span>
                <span className="text-slate-400">•</span>
                <span className="text-slate-600">
                  Nhóm gốc: <strong className="text-slate-800">{tree.name}</strong>
                </span>
                <span className="text-slate-400">•</span>
                <span className="text-slate-600">
                  Kỳ báo cáo: <strong className="text-slate-800">{selectedNode.report_date}</strong>
                </span>
                <span className="text-slate-400">•</span>
                <span className="text-slate-600">
                  Đơn vị: <strong className="text-slate-800">{selectedNode.office_name}</strong>
                </span>
              </div>
              {selectedNode.children.length === 0 && selectedNode.level > 1 && (
                <button
                  type="button"
                  data-testid="inspector-drilldown-leaf"
                  title={`Tra cứu số liệu chỉ tiêu ${selectedNode.name} thuộc nhóm ${tree.name}`}
                  aria-label={`Tra cứu số liệu chỉ tiêu ${selectedNode.name} thuộc nhóm ${tree.name}`}
                  onClick={() => {
                    onClose?.();
                    onSelectChip?.(
                      `Cho tôi biết số liệu chỉ tiêu ${selectedNode.name} thuộc nhóm ${tree.name} ${querySuffix}?`
                    );
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition shadow-xs cursor-pointer"
                >
                  <span>🔍 Tra cứu số liệu</span>
                </button>
              )}
            </>
          ) : (
            <div className="text-[11px] text-slate-500">
              💡 Bấm vào 1–4 ô chỉ tiêu con để <strong>Đối chiếu số liệu trực tiếp tại chỗ (0ms)</strong> hoặc bấm <strong>🔍 Tra cứu số liệu</strong> để xem lịch sử biến động.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

interface InteractiveCriteriaTreeModalProps {
  activeTreeNodes: any[];
  expandAllCounter: number;
  temporalScope?: TemporalScopeMeta;
  onExpandAll: () => void;
  onClose: () => void;
  onSelectChip?: (chip: string) => void;
  onPinItem?: (item: PinnedDrawerItem) => void;
}

const InteractiveCriteriaTreeModal: React.FC<InteractiveCriteriaTreeModalProps> = ({
  activeTreeNodes,
  expandAllCounter,
  temporalScope,
  onExpandAll,
  onClose,
  onSelectChip,
  onPinItem,
}) => {
  const [treeSearchTerm, setTreeSearchTerm] = useState('');
  const [treeStatusFilter, setTreeStatusFilter] = useState<'all' | 'has_value' | 'no_value'>('all');
  const [viewMode, setViewMode] = useState<'tree' | 'compact_table'>('tree');
  const modalTemporalLabel = temporalScope?.label || temporalScope?.period_label || null;

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handlePinTree = () => {
    if (!onPinItem || activeTreeNodes.length === 0) return;
    const firstRoot = activeTreeNodes[0];
    const rootName = cleanDisplayString(firstRoot?.name, 'Sơ đồ cây chỉ tiêu');
    onPinItem({
      id: `pin-tree-${firstRoot?.id || rootName}-${temporalScope?.query_suffix || '2026'}`,
      type: 'tree',
      title: `Cây: ${rootName}`,
      subtitle: `${firstRoot?.office_name || 'Cấp tỉnh'} • ${modalTemporalLabel || 'Năm 2026'}`,
      temporal_scope: temporalScope,
      payload: {
        rootNode: firstRoot,
      },
      pinnedAt: new Date().toISOString(),
    });
  };

  return (
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4"
    >
      <div
        role="dialog"
        aria-modal="true"
        data-testid="interactive-criteria-tree-modal"
        className="bg-white border border-slate-200 rounded-2xl max-w-6xl w-full max-h-[88vh] flex flex-col shadow-2xl overflow-hidden"
      >
        {/* Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 bg-white border-b border-slate-200 shrink-0">
          <div>
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
              <span>Sơ đồ cây phân cấp chỉ tiêu (Cấp 1 ➔ Cấp 2 ➔ Cấp 3)</span>
              {modalTemporalLabel && (
                <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 text-[11px] font-semibold">
                  {modalTemporalLabel}
                </span>
              )}
            </h3>
            <p className="text-[11px] text-slate-500">
              Cột gốc Cấp 1 cố định (Sticky) • Cấp 3 gom cụm Sub-Grid 2 cột • Bấm chọn tối đa 4 nhánh để đối chiếu 0ms
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {/* View Switcher (GP 1.3) */}
            <div
              data-testid="tree-view-switcher"
              className="inline-flex items-center rounded-lg bg-slate-100 p-0.5 border border-slate-200"
            >
              <button
                type="button"
                data-testid="tree-view-mode-diagram"
                onClick={() => setViewMode('tree')}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer ${
                  viewMode === 'tree'
                    ? 'bg-white text-indigo-700 shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                🌳 Sơ đồ cây
              </button>
              <button
                type="button"
                data-testid="tree-view-mode-table"
                onClick={() => setViewMode('compact_table')}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition cursor-pointer ${
                  viewMode === 'compact_table'
                    ? 'bg-white text-indigo-700 shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                📋 Bảng thu gọn
              </button>
            </div>

            {onPinItem && (
              <button
                type="button"
                data-testid="pin-tree-modal-button"
                onClick={handlePinTree}
                title="Ghim cây chỉ tiêu này sang khay tham chiếu bên phải (Split-Screen)"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-xs font-semibold transition cursor-pointer"
              >
                <Pin className="w-3.5 h-3.5" />
                <span>📌 Ghim sang khay phải</span>
              </button>
            )}

            <button
              type="button"
              onClick={onExpandAll}
              className="px-2.5 py-1 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium transition cursor-pointer"
            >
              Mở rộng tất cả
            </button>
            <button
              type="button"
              onClick={onClose}
              title="Đóng cửa sổ (X)"
              aria-label="Đóng cửa sổ"
              className="w-8 h-8 rounded-lg bg-white hover:bg-rose-50 text-slate-500 hover:text-rose-600 border border-slate-200 flex items-center justify-center font-bold text-sm transition cursor-pointer"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Sub-Toolbar: Ancestor-Preserving Quick Search + Status Filter Pills (GP 1.3) */}
        <div className="px-5 py-2.5 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div className="relative flex-1 min-w-[220px] max-w-sm">
            <input
              type="text"
              data-testid="tree-search-input"
              value={treeSearchTerm}
              onChange={(e) => setTreeSearchTerm(e.target.value)}
              placeholder="Tìm nhanh nhánh con (hỗ trợ gõ không dấu)..."
              className="w-full pl-8 pr-7 py-1.5 text-xs rounded-lg border border-slate-200 bg-white text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            {treeSearchTerm && (
              <button
                type="button"
                onClick={() => setTreeSearchTerm('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div
            data-testid="tree-status-filter"
            className="flex flex-wrap items-center gap-1.5"
          >
            <span className="text-[11px] font-semibold text-slate-500 mr-1">Lọc nhánh:</span>
            <button
              type="button"
              data-testid="tree-filter-all"
              onClick={() => setTreeStatusFilter('all')}
              className={`px-2.5 py-1 rounded-full text-xs font-semibold border transition cursor-pointer ${
                treeStatusFilter === 'all'
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
              }`}
            >
              Tất cả
            </button>
            <button
              type="button"
              data-testid="tree-filter-has-value"
              onClick={() => setTreeStatusFilter('has_value')}
              className={`px-2.5 py-1 rounded-full text-xs font-semibold border transition cursor-pointer ${
                treeStatusFilter === 'has_value'
                  ? 'bg-emerald-600 text-white border-emerald-600'
                  : 'bg-white text-slate-700 border-slate-200 hover:bg-emerald-50'
              }`}
            >
              ⚡ Đã có số liệu
            </button>
            <button
              type="button"
              data-testid="tree-filter-no-value"
              onClick={() => setTreeStatusFilter('no_value')}
              className={`px-2.5 py-1 rounded-full text-xs font-semibold border transition cursor-pointer ${
                treeStatusFilter === 'no_value'
                  ? 'bg-amber-600 text-white border-amber-600'
                  : 'bg-white text-slate-700 border-slate-200 hover:bg-amber-50'
              }`}
            >
              Chưa có số liệu (-)
            </button>
            {(treeSearchTerm || treeStatusFilter !== 'all') && (
              <button
                type="button"
                data-testid="tree-filter-reset"
                onClick={() => {
                  setTreeSearchTerm('');
                  setTreeStatusFilter('all');
                }}
                className="px-2 py-1 rounded-lg bg-rose-50 text-rose-700 border border-rose-200 text-[11px] font-semibold hover:bg-rose-100 transition cursor-pointer"
              >
                Xóa bộ lọc
              </button>
            )}
          </div>
        </div>

        {/* Canvas Body */}
        <div className="p-5 overflow-y-auto overflow-x-auto space-y-4 bg-white flex-1">
          {activeTreeNodes.map((rootNode: any, idx: number) => (
            <InteractiveCriteriaTreeCanvas
              key={rootNode.id || idx}
              rawRoot={rootNode}
              globalExpandSignal={expandAllCounter}
              treeSearchTerm={treeSearchTerm}
              treeStatusFilter={treeStatusFilter}
              viewMode={viewMode}
              temporalScope={temporalScope}
              onSelectChip={onSelectChip}
              onClose={onClose}
              onResetFilter={() => {
                setTreeSearchTerm('');
                setTreeStatusFilter('all');
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export const SmartTable: React.FC<SmartTableProps> = ({
  tabularData,
  children,
  onSelectChip,
  onPinItem,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [copied, setCopied] = useState(false);
  const [activeTreeRootId, setActiveTreeRootId] = useState<string | null>(null);
  const [expandAllCounter, setExpandAllCounter] = useState(0);
  // Feature 5 (Đề xuất 6): 1-Click Quick Filter Toggle Pills (0ms Client-side)
  const [quickFilter, setQuickFilter] = useState<
    'all' | 'has_value' | 'has_children' | 'has_diff' | 'draft_only' | 'approved_only'
  >('all');
  const [contextCustomDate, setContextCustomDate] = useState<string>('');

  // Xác định cấu trúc cột và dòng
  const { columns, rows, title, treeModal, isPrimaryTable } = useMemo(
    () => resolveSmartTableData(tabularData, children),
    [tabularData, children]
  );

  const temporalScope: TemporalScopeMeta | undefined = (tabularData as any)?.temporal_scope;
  const temporalLabel = temporalScope?.label || temporalScope?.period_label || null;
  const contextQueryTemplate: string | undefined = (tabularData as any)?.context_query_template;

  // Nhận diện loại bảng để hiển thị đúng bộ Quick Filter Pills (Feature 5 - Đề xuất 6)
  const tableFilterCategory = useMemo((): 'criteria' | 'audit' | 'none' => {
    if (!columns || columns.length === 0) return 'none';
    const colKeys = columns.map((c) => String(c.key || '').toLowerCase().trim());
    const colLabels = columns.map((c) => String(c.label || '').toLowerCase().trim());

    // Bảng đối soát / trạng thái báo cáo (REQ-Q05 / SC-5.1a / SC-5.1b / SC-5.1c / SC-5.2)
    const isAudit =
      colKeys.some((k) =>
        [
          'diff',
          'diff_display',
          'chenh_lech',
          'draft_value',
          'approved_value',
          'report_status',
          'status_display',
          'group_status',
          'draft_criteria_count',
          'trang_thai_bao_cao',
        ].includes(k)
      ) ||
      colLabels.some(
        (l) =>
          l.includes('chênh lệch') ||
          l.includes('bản nháp') ||
          l.includes('chỉ tiêu nháp') ||
          l.includes('trạng thái phê duyệt') ||
          l.includes('trạng thái báo cáo') ||
          (l === 'trạng thái' &&
            colLabels.some(
              (l2) =>
                l2.includes('kỳ báo cáo') ||
                l2.includes('ngày nộp') ||
                l2.includes('biểu mẫu') ||
                l2.includes('nhóm thu thập') ||
                l2.includes('chỉ tiêu đã duyệt')
            ))
      );
    if (isAudit) return 'audit';

    // Bảng chỉ tiêu phân cấp / tra cứu chỉ tiêu (REQ-Q01 / REQ-Q04 / REQ-Q02 / SC-2.1)
    const hasTreeModalData = Boolean(treeModal && Object.keys(treeModal).length > 0);
    const isCriteria =
      hasTreeModalData ||
      colKeys.some((k) =>
        [
          'ten_chi_tieu',
          'criteria_name',
          'gia_tri',
          'gia_tri_moi_nhat',
          'chi_tiet_con',
          'child_action',
        ].includes(k)
      ) ||
      colLabels.some(
        (l) =>
          l.includes('tên chỉ tiêu') ||
          l.includes('chỉ tiêu gốc') ||
          l.includes('chỉ tiêu con') ||
          l.includes('số lượng / giá trị') ||
          l.includes('giá trị mới nhất')
      );
    if (isCriteria) return 'criteria';

    return 'none';
  }, [columns, treeModal]);

  // Kiểm tra xem bảng hiện tại có phải là Bảng Danh Sách Nhiệm Vụ (REQ-Q03) hay không
  const isMissionListingTable = useMemo(() => {
    if (!columns || columns.length === 0) return false;
    const hasTreeModalData = Boolean(treeModal && Object.keys(treeModal).length > 0);
    if (hasTreeModalData) return false;

    const colKeys = columns.map((c) => String(c.key || '').toLowerCase().trim());
    const colLabels = columns.map((c) => String(c.label || '').toLowerCase().trim());

    const isFactOrCriteriaTable =
      colKeys.some((k) =>
        [
          'ten_chi_tieu',
          'criteria_name',
          'criteria_code',
          'gia_tri',
          'gia_tri_moi_nhat',
          'structure_type',
          'loai_cau_truc',
          'nhom_chi_tieu',
        ].includes(k)
      ) ||
      colLabels.some(
        (l) =>
          l.includes('tên chỉ tiêu') ||
          l.includes('chỉ tiêu /') ||
          l.includes('giá trị mới nhất') ||
          l === 'giá trị' ||
          l.includes('loại cấu trúc') ||
          l.includes('nhóm chỉ tiêu')
      );
    if (isFactOrCriteriaTable) return false;

    const isReportOrPersonnelTable =
      colKeys.some((k) =>
        [
          'report_code',
          'ma_bao_cao',
          'report_name',
          'ten_bao_cao',
          'report_status',
          'trang_thai_bao_cao',
          'report_date',
          'submitted_date',
          'full_name',
          'user_name',
          'ho_ten',
          'ten_can_bo',
          'chuc_vu',
          'position',
        ].includes(k)
      ) ||
      colLabels.some(
        (l) =>
          l.includes('mã báo cáo') ||
          l.includes('tên báo cáo') ||
          l.includes('trạng thái phê duyệt') ||
          l.includes('kỳ báo cáo') ||
          l.includes('ngày nộp') ||
          l.includes('họ và tên') ||
          l.includes('cán bộ') ||
          l.includes('chức vụ')
      );
    if (isReportOrPersonnelTable) return false;

    const hasMissionNameCol =
      colKeys.some((k) => ['mission_name', 'ten_nhiem_vu', 'nhiem_vu', 'mission'].includes(k)) ||
      colLabels.some(
        (l) =>
          l.includes('tên nhiệm vụ') ||
          l === 'nhiệm vụ' ||
          l === 'nhiệm vụ trọng tâm' ||
          l === 'nhiệm vụ phụ trách'
      );

    const hasMissionMetaCol =
      colKeys.some((k) =>
        [
          'mission_code',
          'ma_nhiem_vu',
          'code',
          'total_criteria_count',
          'level1_group_count',
          'scope',
          'scope_name',
          'linh_vuc',
        ].includes(k)
      ) ||
      colLabels.some(
        (l) =>
          l.includes('mã nhiệm vụ') ||
          l.includes('lĩnh vực') ||
          l.includes('tổng số chỉ tiêu') ||
          l.includes('nhóm cấp 1') ||
          l.includes('đơn vị phụ trách')
      );

    return hasMissionNameCol && hasMissionMetaCol;
  }, [columns, treeModal]);

  // Kiểm tra hiển thị Thanh Ticket Thời Gian (Context Ticket Bar — Feature 4 Mở rộng cho SC-2.1, REQ-Q01, REQ-Q04, REQ-Q03)
  const showContextTicketBar = useMemo(() => {
    if (!isPrimaryTable || !onSelectChip) return false;
    if (contextQueryTemplate) return true;
    if (Array.isArray((tabularData as any)?.multi_parent_rows)) return true;
    if (isMissionListingTable) return true;
    if (tableFilterCategory === 'criteria') return true;
    return false;
  }, [isPrimaryTable, onSelectChip, contextQueryTemplate, tabularData, isMissionListingTable, tableFilterCategory]);

  const dispatchContextTicket = useCallback(
    (periodPhrase: string) => {
      if (!onSelectChip) return;
      if (contextQueryTemplate) {
        onSelectChip(contextQueryTemplate.replace('{period}', periodPhrase));
        return;
      }
      const cleanTitle = cleanDisplayString(title);
      if (
        Array.isArray((tabularData as any)?.multi_parent_rows) ||
        cleanTitle.toLowerCase().includes('đối chiếu chỉ tiêu')
      ) {
        const match = cleanTitle.match(/'([^']+)'/);
        const critName = match?.[1] || cleanDisplayString(rows[0]?.item) || 'Trồng trọt';
        onSelectChip(`Chỉ tiêu ${critName} ${periodPhrase} là bao nhiêu?`);
        return;
      }
      if (isMissionListingTable) {
        onSelectChip(`Danh mục các nhiệm vụ trọng tâm ${periodPhrase} của tỉnh Lâm Đồng?`);
        return;
      }
      const missionMatch = cleanTitle.match(/thuộc nhiệm vụ\s+([^\n(]+?)(?:\s+năm|\s+trong|\s+tại|$)/i);
      if (missionMatch?.[1]) {
        onSelectChip(
          `Hiển thị các chỉ tiêu Cấp 1 của nhiệm vụ ${missionMatch[1].trim()} ${periodPhrase}?`
        );
        return;
      }
      onSelectChip(`Danh sách các chỉ tiêu Cấp 1 đã được phê duyệt ${periodPhrase}?`);
    },
    [onSelectChip, contextQueryTemplate, title, tabularData, rows, isMissionListingTable]
  );

  // Lọc dữ liệu theo Quick Filter Pills (Feature 5) + từ khóa tìm kiếm (hỗ trợ không dấu)
  const filteredRows = useMemo(() => {
    let base = rows;

    if (quickFilter !== 'all') {
      base = base.filter((r) => {
        const allVals = Object.entries(r).map(([k, v]) => ({
          k: k.toLowerCase(),
          v: cleanDisplayString(v),
        }));

        if (quickFilter === 'has_value') {
          // Tìm cột giá trị / số lượng
          const valCol = columns.find((c) => {
            const kl = String(c.key || '').toLowerCase();
            const ll = String(c.label || '').toLowerCase();
            return (
              kl.includes('gia_tri') ||
              kl.includes('value') ||
              ll.includes('giá trị') ||
              ll.includes('số lượng')
            );
          });
          if (valCol) {
            return hasValidMetricValue(r[valCol.key]);
          }
          return allVals.some((x) => hasValidMetricValue(x.v));
        }

        if (quickFilter === 'has_children') {
          return (
            Boolean(r.has_children) ||
            Boolean(r.is_parent) ||
            Boolean(r.is_parent_group) ||
            Number(r.child_count || 0) > 0 ||
            allVals.some(
              (x) =>
                x.v.includes('Xem chi tiết các chỉ tiêu con') ||
                x.v.includes('Xem chi tiết con') ||
                x.v.includes('chỉ tiêu con') ||
                x.v.includes('Nhóm chỉ tiêu cha')
            )
          );
        }

        if (quickFilter === 'has_diff') {
          const diffCol = columns.find((c) => {
            const kl = String(c.key || '').toLowerCase();
            const ll = String(c.label || '').toLowerCase();
            return kl.includes('diff') || kl.includes('chenh_lech') || ll.includes('chênh lệch');
          });
          if (diffCol) {
            const dv = cleanDisplayString(r[diffCol.key]).toLowerCase();
            return (
              dv !== '' &&
              dv !== '0' &&
              dv !== '+0' &&
              dv !== '-0' &&
              !dv.startsWith('0 (khớp') &&
              dv !== 'khớp' &&
              dv !== '-'
            );
          }
          const draftValCol = columns.find((c) => {
            const kl = String(c.key || '').toLowerCase();
            const ll = String(c.label || '').toLowerCase();
            return kl.includes('draft_value') || ll.includes('giá trị bản nháp') || ll.includes('giá trị nháp');
          });
          if (draftValCol) {
            const dv = cleanDisplayString(r[draftValCol.key]).toLowerCase();
            return hasValidMetricValue(dv) && !dv.includes('chưa nhập');
          }
          return allVals.some(
            (x) =>
              x.v.includes('+') ||
              x.v.includes('Lệch') ||
              x.v.includes('lệch') ||
              x.v.includes('Chưa có bản duyệt')
          );
        }

        if (quickFilter === 'draft_only') {
          if (String(r.raw_status || '').toUpperCase() === 'DRAFT') return true;
          if (Number(r.draft_criteria_count || 0) > 0 && String(r.status_display || '').toLowerCase().includes('nháp')) {
            return true;
          }
          return allVals.some((x) => {
            const lv = x.v.toLowerCase();
            return (
              lv.includes('draft') ||
              lv.includes('bản nháp') ||
              lv.includes('dự thảo') ||
              lv.includes('chưa nộp') ||
              lv.includes('chưa phê duyệt')
            );
          });
        }

        if (quickFilter === 'approved_only') {
          if (String(r.raw_status || '').toUpperCase() === 'APPROVED') return true;
          return allVals.some((x) => {
            const lv = x.v.toLowerCase();
            return (
              lv.includes('approved') ||
              lv.includes('đã phê duyệt')
            );
          });
        }

        return true;
      });
    }

    if (!searchTerm.trim()) return base;
    const termNorm = removeVietnameseTones(searchTerm);
    const expandSearchNorm = (raw: string) =>
      removeVietnameseTones(raw)
        .replace(/\blhhtx\b/g, 'lhhtx lien hiep hop tac xa')
        .replace(/\bhtx\b/g, 'htx hop tac xa')
        .replace(/\btht\b/g, 'tht to hop tac');
    return base.filter((r) =>
      Object.values(r).some((val) => expandSearchNorm(String(val ?? '')).includes(termNorm))
    );
  }, [rows, searchTerm, quickFilter, columns]);

  // Sắp xếp dữ liệu theo cột được chọn
  const sortedRows = useMemo(() => {
    if (!sortKey) return filteredRows;
    const colConfig = columns.find((c) => c.key === sortKey);
    const isNum = colConfig?.data_type === 'number';

    const parseVnNum = (v: any): number => {
      const cleaned = cleanDisplayString(v).replace(/\s*\([^)]*\)\s*/g, '').trim();
      if (/^[+-]?\d{1,3}(\.\d{3})+(,\d+)?$/.test(cleaned)) {
        return parseFloat(cleaned.replace(/\./g, '').replace(',', '.')) || 0;
      }
      return parseFloat(cleaned.replace(/,/g, '')) || 0;
    };

    return [...filteredRows].sort((a, b) => {
      const valA = a[sortKey];
      const valB = b[sortKey];
      if (valA === valB) return 0;
      if (valA === undefined || valA === null) return 1;
      if (valB === undefined || valB === null) return -1;

      if (isNum) {
        const numA = parseVnNum(valA);
        const numB = parseVnNum(valB);
        return sortOrder === 'asc' ? numA - numB : numB - numA;
      }

      const strA = String(valA).toLowerCase();
      const strB = String(valB).toLowerCase();
      return sortOrder === 'asc' ? strA.localeCompare(strB, 'vi') : strB.localeCompare(strA, 'vi');
    });
  }, [filteredRows, sortKey, sortOrder, columns]);

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

  const handlePinTable = () => {
    if (!onPinItem) return;
    const tableTitle = title || 'Bảng số liệu thống kê';
    onPinItem({
      id: `pin-table-${tableTitle}-${temporalScope?.query_suffix || rows.length}`,
      type: 'table',
      title: tableTitle,
      subtitle: `${rows.length} bản ghi • ${temporalLabel || 'Năm 2026'}`,
      temporal_scope: temporalScope,
      payload: {
        columns,
        rows,
      },
      pinnedAt: new Date().toISOString(),
    });
  };

  const activeTreeNodes = useMemo(() => {
    if (!activeTreeRootId) return [];
    const mapObj = treeModal || {};
    if (mapObj && mapObj[activeTreeRootId]) {
      return [mapObj[activeTreeRootId]];
    }
    const vals: any[] = Object.values(mapObj || {});
    const targetClean = cleanDisplayString(activeTreeRootId).toLowerCase();
    const byIdOrName = vals.filter((n) => {
      if (!n) return false;
      const nId = cleanDisplayString(n.id).toLowerCase();
      const nCode = cleanDisplayString(n.code).toLowerCase();
      const nName = cleanDisplayString(n.name).toLowerCase();
      return nId === targetClean || nCode === targetClean || nName === targetClean;
    });
    if (byIdOrName.length > 0) return byIdOrName;
    return vals.length > 0 ? vals : [];
  }, [activeTreeRootId, treeModal]);

  if (columns.length === 0) {
    return (
      <div className="not-prose my-3 inline-block max-w-full overflow-x-auto rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <table className="w-auto text-sm border-collapse divide-y divide-slate-200 [&_th]:border [&_th]:border-slate-200 [&_th]:bg-slate-50 [&_th]:px-3 [&_th]:py-2 [&_th]:font-semibold [&_th]:text-slate-700 [&_td]:border [&_td]:border-slate-200 [&_td]:px-3 [&_td]:py-2 [&_td]:text-slate-800">
          {children}
        </table>
      </div>
    );
  }

  return (
    <div className="not-prose my-3 inline-block w-fit max-w-full rounded-xl border border-slate-200/90 bg-white shadow-sm overflow-hidden transition-all duration-200 hover:shadow-md">
      {/* 1. Header Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 px-3.5 py-2.5 bg-gradient-to-r from-slate-50 to-indigo-50/30 border-b border-slate-200">
        <div className="flex flex-wrap items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
            <TableIcon className="w-3.5 h-3.5" />
          </div>
          <span className="text-xs font-semibold text-slate-800">
            {title || 'Bảng số liệu thống kê chi tiết'}
          </span>
          <span
            data-testid="smart-table-row-count"
            className="text-[11px] px-2 py-0.5 rounded-full bg-slate-200/70 text-slate-600 font-medium"
          >
            {filteredRows.length} bản ghi
          </span>
          {isPrimaryTable && temporalLabel && (
            <span
              data-testid="smart-table-temporal-badge"
              className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-semibold"
            >
              <Clock className="w-3 h-3" />
              {temporalLabel}
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1.5 ml-auto">
          {/* Ô tìm kiếm nhanh */}
          {rows.length > 2 && (
            <div className="relative">
              <input
                type="text"
                data-testid="smart-table-search-input"
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                }}
                placeholder="Lọc dòng..."
                className="w-28 sm:w-36 pl-7 pr-2 py-1 text-xs rounded-lg border border-slate-200 bg-white text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 transition"
              />
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2 top-1/2 -translate-y-1/2" />
            </div>
          )}

          {/* Nút Ghim sang Khay Tham Chiếu (Feature 2 Tier 2) */}
          {onPinItem && (
            <button
              type="button"
              data-testid="pin-item-button"
              onClick={handlePinTable}
              title="Ghim bảng số liệu này sang khay tham chiếu bên phải (Split-Screen)"
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition shadow-2xs cursor-pointer"
            >
              <Pin className="w-3.5 h-3.5" />
              <span>📌 Ghim</span>
            </button>
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

      {/* 1.25. Thanh Ticket Thời Gian (Context Ticket Bar — Feature 4 Mở rộng cho SC-2.1, REQ-Q01, REQ-Q04, REQ-Q03) */}
      {showContextTicketBar && (
        <div
          data-testid="smart-table-context-ticket-bar"
          className="px-3.5 py-2 bg-indigo-50/40 border-b border-slate-200/80 flex flex-wrap items-center justify-between gap-2"
        >
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-700 mr-1">
              <Clock className="w-3 h-3" />
              Ticket thời gian:
            </span>
            {[
              { id: 'year', label: 'Năm 2026 (Mới nhất)', phrase: 'năm 2026' },
              { id: 'q1', label: 'Quý 1', phrase: 'trong Quý 1 năm 2026' },
              { id: 'q2', label: 'Quý 2', phrase: 'trong Quý 2 năm 2026' },
              { id: 'q3', label: 'Quý 3', phrase: 'trong Quý 3 năm 2026' },
            ].map((tk) => {
              const activeSuffix = (temporalScope?.query_suffix || 'năm 2026').toLowerCase();
              const isTkActive =
                tk.id === 'year'
                  ? activeSuffix === 'năm 2026'
                  : activeSuffix.includes(tk.label.toLowerCase());
              return (
                <button
                  key={tk.id}
                  type="button"
                  data-testid={`context-ticket-${tk.id}`}
                  onClick={() => dispatchContextTicket(tk.phrase)}
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold border transition cursor-pointer ${
                    isTkActive
                      ? 'bg-indigo-600 text-white border-indigo-600 shadow-2xs'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-indigo-50 hover:border-indigo-300'
                  }`}
                >
                  {tk.label}
                </button>
              );
            })}
          </div>
          <div className="flex items-center gap-1.5">
            <input
              type="date"
              data-testid="context-ticket-date-input"
              value={contextCustomDate}
              onChange={(e) => setContextCustomDate(e.target.value)}
              className="px-2 py-0.5 text-[11px] rounded-md border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            <button
              type="button"
              data-testid="context-ticket-date-apply"
              onClick={() => {
                if (!contextCustomDate.trim()) return;
                const trimmed = contextCustomDate.trim();
                const parts = trimmed.split('-');
                const vnDate =
                  parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : trimmed;
                dispatchContextTicket(`tính đến ngày ${vnDate} năm 2026`);
              }}
              className="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-white hover:bg-indigo-50 text-indigo-700 border border-indigo-200 transition cursor-pointer"
            >
              Tùy chỉnh ngày
            </button>
          </div>
        </div>
      )}

      {/* 1.5. Thanh 1-Click Quick Filter Toggle Pills (Feature 5 — Đề xuất 6: 0ms Client-side) */}
      {tableFilterCategory !== 'none' && rows.length > 1 && (
        <div
          data-testid="smart-table-quick-filters"
          className="px-3.5 py-2 bg-slate-50/90 border-b border-slate-200/80 flex flex-wrap items-center justify-between gap-2"
        >
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-500 mr-1">
              <Filter className="w-3 h-3 text-indigo-600" />
              Lọc nhanh 0ms:
            </span>

            <button
              type="button"
              data-testid="table-filter-all"
              onClick={() => setQuickFilter('all')}
              className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold border transition cursor-pointer ${
                quickFilter === 'all'
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
              }`}
            >
              Tất cả ({rows.length})
            </button>

            {tableFilterCategory === 'criteria' && (
              <>
                <button
                  type="button"
                  data-testid="table-filter-has-value"
                  onClick={() => setQuickFilter('has_value')}
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold border transition cursor-pointer ${
                    quickFilter === 'has_value'
                      ? 'bg-emerald-600 text-white border-emerald-600'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-emerald-50'
                  }`}
                >
                  ⚡ Đã có số liệu
                </button>
                <button
                  type="button"
                  data-testid="table-filter-has-children"
                  onClick={() => setQuickFilter('has_children')}
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold border transition cursor-pointer ${
                    quickFilter === 'has_children'
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-indigo-50'
                  }`}
                >
                  🌳 Có chỉ tiêu con
                </button>
              </>
            )}

            {tableFilterCategory === 'audit' && (
              <>
                <button
                  type="button"
                  data-testid="table-filter-approved-only"
                  onClick={() => setQuickFilter('approved_only')}
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold border transition cursor-pointer ${
                    quickFilter === 'approved_only'
                      ? 'bg-emerald-600 text-white border-emerald-600'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-emerald-50'
                  }`}
                >
                  ✅ Đã phê duyệt
                </button>
                <button
                  type="button"
                  data-testid="table-filter-draft-only"
                  onClick={() => setQuickFilter('draft_only')}
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold border transition cursor-pointer ${
                    quickFilter === 'draft_only'
                      ? 'bg-rose-600 text-white border-rose-600'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-rose-50'
                  }`}
                >
                  ⚠️ Bản nháp chưa nộp
                </button>
                <button
                  type="button"
                  data-testid="table-filter-has-diff"
                  onClick={() => setQuickFilter('has_diff')}
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold border transition cursor-pointer ${
                    quickFilter === 'has_diff'
                      ? 'bg-amber-600 text-white border-amber-600'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-amber-50'
                  }`}
                >
                  ⚡ Chỉ hiện dòng có chênh lệch
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* 2. Khung cuộn bảng dữ liệu */}
      <div className="overflow-x-auto overflow-y-auto max-h-[520px] max-w-full">
        <table className="w-auto text-left border-collapse text-[13px]">
          <thead className="sticky top-0 z-10 bg-slate-100 border-b border-slate-200">
            <tr className="bg-slate-100/95 border-b border-slate-200 text-slate-700 select-none divide-x divide-slate-200/70">
              {columns.map((col) => {
                const isSorted = sortKey === col.key;
                const isStt = col.key === 'stt' || col.label.toUpperCase() === 'STT';
                return (
                  <th
                    key={col.key}
                    onClick={() => handleSort(col.key)}
                    className={`py-2 px-3 text-[11px] font-semibold uppercase tracking-wide cursor-pointer hover:bg-slate-200/70 transition-colors whitespace-nowrap ${
                      isStt ? 'text-center w-12' : 'text-left'
                    }`}
                  >
                    <div
                      className={`inline-flex items-center gap-1 ${
                        isStt ? 'justify-center' : 'justify-start'
                      }`}
                    >
                      <span>{col.label}</span>
                      {isSorted ? (
                        sortOrder === 'asc' ? (
                          <ArrowUp className="w-3 h-3 text-blue-600" />
                        ) : (
                          <ArrowDown className="w-3 h-3 text-blue-600" />
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
            {sortedRows.length > 0 ? (
              sortedRows.map((row, rIdx) => {
                const criteriaNameCol = columns.find((c) => {
                  const k = String(c.key || '').toLowerCase().trim();
                  const l = String(c.label || '').toLowerCase().trim();
                  return (
                    k === 'item' ||
                    k === 'ten_chi_tieu' ||
                    k === 'criteria_name' ||
                    l.includes('tên chỉ tiêu')
                  );
                });
                const fallbackCriterionName = criteriaNameCol
                  ? cleanDisplayString(row[criteriaNameCol.key])
                  : '';
                const resolvedTreeRootId =
                  row.tree_root_id ||
                  row.criteria_id ||
                  row.root_id ||
                  fallbackCriterionName ||
                  'ALL';

                return (
                  <tr
                    key={`r-${rIdx}`}
                    className="odd:bg-white even:bg-slate-50/50 hover:bg-indigo-50/40 transition-colors duration-150 divide-x divide-slate-100"
                  >
                    {columns.map((col) => {
                      const cellVal = row[col.key];
                      const cleanVal = cleanDisplayString(cellVal);
                      const isTreeTrigger =
                        cleanVal.includes('Xem chi tiết các chỉ tiêu con') ||
                        cleanVal.includes('Xem chi tiết con') ||
                        cleanVal.includes('chi tiết chỉ tiêu con');
                      const isStt = col.key === 'stt' || col.label.toUpperCase() === 'STT';
                      const colKeyLower = String(col.key || '').toLowerCase().trim();
                      const colLabelLower = String(col.label || '').toLowerCase().trim();
                      const isMissionNameCell =
                        isMissionListingTable &&
                        !colLabelLower.includes('mã') &&
                        !colKeyLower.includes('code') &&
                        !colKeyLower.includes('id') &&
                        (colKeyLower === 'mission_name' ||
                          colKeyLower === 'ten_nhiem_vu' ||
                          colKeyLower === 'nhiem_vu' ||
                          colKeyLower === 'mission' ||
                          colLabelLower.includes('tên nhiệm vụ') ||
                          colLabelLower === 'nhiệm vụ' ||
                          colLabelLower === 'nhiệm vụ trọng tâm' ||
                          colLabelLower === 'nhiệm vụ phụ trách') &&
                        Boolean(cleanVal) &&
                        cleanVal !== '-';

                      return (
                        <td
                          key={`c-${col.key}`}
                          className={`py-2 px-3 align-middle ${
                            isStt
                              ? 'text-center w-12 whitespace-nowrap'
                              : 'text-left max-w-[320px] break-words'
                          }`}
                        >
                          {isTreeTrigger ? (
                            <button
                              type="button"
                              data-testid={`open-tree-modal-${rIdx}`}
                              onClick={() => setActiveTreeRootId(resolvedTreeRootId)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-xs font-semibold transition cursor-pointer whitespace-nowrap"
                              title="Bấm để mở sơ đồ cây phân cấp chỉ tiêu con"
                            >
                              <span>🌳 - Xem chi tiết các chỉ tiêu con</span>
                            </button>
                          ) : isMissionNameCell ? (
                            <button
                              type="button"
                              data-testid={`drilldown-mission-${rIdx}`}
                              data-mission-name={cleanVal}
                              onClick={() =>
                                onSelectChip?.(
                                  `Hiển thị các chỉ tiêu cấp 1 của nhiệm vụ ${cleanVal} ${
                                    temporalScope?.query_suffix || 'năm 2026'
                                  }?`
                                )
                              }
                              title={`Xem các chỉ tiêu Cấp 1 của nhiệm vụ ${cleanVal}`}
                              aria-label={`Xem chỉ tiêu Cấp 1 của nhiệm vụ ${cleanVal}`}
                              className="group inline-flex flex-wrap items-center gap-2 text-left py-0.5 px-1.5 -mx-1.5 rounded-lg hover:bg-indigo-50/80 transition cursor-pointer"
                            >
                              <span className="font-semibold text-slate-900 group-hover:text-indigo-700 underline decoration-indigo-300 underline-offset-2 transition-colors">
                                {cleanVal}
                              </span>
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-indigo-50 group-hover:bg-indigo-600 text-indigo-700 group-hover:text-white border border-indigo-200 group-hover:border-indigo-600 text-[11px] font-semibold transition-all shadow-2xs whitespace-nowrap">
                                🔍 Xem chỉ tiêu Cấp 1
                              </span>
                            </button>
                          ) : (
                            renderCellContent(cellVal, col)
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={columns.length} className="text-center py-6 text-slate-400 text-xs italic">
                  <div className="space-y-2">
                    <div>Không tìm thấy dòng số liệu nào khớp với bộ lọc hiện tại.</div>
                    {(quickFilter !== 'all' || searchTerm) && (
                      <button
                        type="button"
                        data-testid="smart-table-reset-filter"
                        onClick={() => {
                          setQuickFilter('all');
                          setSearchTerm('');
                        }}
                        className="px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-semibold hover:bg-indigo-100 transition cursor-pointer not-italic"
                      >
                        Khôi phục toàn bộ ({rows.length} dòng)
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 3. Pop-up Tree Modal Nền Trắng Tối Giản Tương Tác */}
      {activeTreeRootId && (
        <InteractiveCriteriaTreeModal
          activeTreeNodes={activeTreeNodes}
          expandAllCounter={expandAllCounter}
          temporalScope={temporalScope}
          onExpandAll={() => setExpandAllCounter((c) => c + 1)}
          onClose={() => setActiveTreeRootId(null)}
          onSelectChip={onSelectChip}
          onPinItem={onPinItem}
        />
      )}
    </div>
  );
};
