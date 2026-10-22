'use client';

import React, { useState, useMemo, useRef, useLayoutEffect, useCallback, useEffect } from 'react';
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
  ChevronDown,
  Table as TableIcon,
} from 'lucide-react';

interface SmartTableProps {
  tabularData?: TabularData;
  children?: React.ReactNode;
  onSelectChip?: (chip: string) => void;
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
          // Coi dòng tr đầu tiên là header
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
    };
  }

  // Các bảng Markdown thứ 2, thứ 3 (khác header hoặc khác số dòng) render đúng mdColumns và mdRows của chính nó
  return {
    columns: mdColumns,
    rows: mdRows,
    title: undefined,
    treeModal: {},
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

  // Nhận diện Badge trạng thái công vụ (approved / active / mặc định cột badge)
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

interface NormalizedTreeNode {
  uid: string;
  parentId: string | null;
  level: 1 | 2 | 3;
  name: string;
  value: any;
  office_name: string;
  mission_name: string;
  children: NormalizedTreeNode[];
}

function cleanDisplayString(val: any, fallback = ''): string {
  if (val === null || val === undefined) return fallback;
  return String(val).replace(/^\*\*|\*\*$/g, '').replace(/^`|`$/g, '').trim() || fallback;
}

function normalizeTreeData(rawRoot: any): NormalizedTreeNode {
  const rootName = cleanDisplayString(rawRoot?.name, 'Nhóm chỉ tiêu Cấp 1');
  const rootUid = String(rawRoot?.id || rawRoot?.code || `l1-${rootName || 'root'}`);
  const rawL2: any[] = Array.isArray(rawRoot?.children) ? rawRoot.children : [];

  const l2Nodes: NormalizedTreeNode[] = rawL2.map((c2: any, idx2: number) => {
    const l2Uid = String(c2?.id || c2?.code || `${rootUid}-l2-${idx2}`);
    const rawL3: any[] = Array.isArray(c2?.children) ? c2.children : [];
    const l3Nodes: NormalizedTreeNode[] = rawL3.map((c3: any, idx3: number) => ({
      uid: String(c3?.id || c3?.code || `${l2Uid}-l3-${idx3}`),
      parentId: l2Uid,
      level: 3,
      name: cleanDisplayString(c3?.name, 'Chỉ tiêu Cấp 3'),
      value: c3?.value,
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
      level: 2,
      name: cleanDisplayString(c2?.name, 'Chỉ tiêu Cấp 2'),
      value: c2?.value,
      office_name: cleanDisplayString(c2?.office_name || rawRoot?.office_name, 'Cấp tỉnh'),
      mission_name: cleanDisplayString(c2?.mission_name || rawRoot?.mission_name, ''),
      children: l3Nodes,
    };
  });

  return {
    uid: rootUid,
    parentId: null,
    level: 1,
    name: rootName,
    value: rawRoot?.value,
    office_name: cleanDisplayString(rawRoot?.office_name, 'Cấp tỉnh'),
    mission_name: cleanDisplayString(rawRoot?.mission_name, ''),
    children: l2Nodes,
  };
}

const InteractiveCriteriaTreeCanvas: React.FC<{
  rawRoot: any;
  globalExpandSignal?: number;
  onSelectChip?: (chip: string) => void;
  onClose?: () => void;
}> = ({ rawRoot, globalExpandSignal, onSelectChip, onClose }) => {
  const tree = useMemo(() => normalizeTreeData(rawRoot), [rawRoot]);
  const [collapsedIds, setCollapsedIds] = useState<Record<string, boolean>>({});
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

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

  useEffect(() => {
    if (globalExpandSignal !== undefined && globalExpandSignal > 0) {
      setCollapsedIds({});
    }
  }, [globalExpandSignal]);

  const toggleCollapse = useCallback((uid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCollapsedIds((prev) => ({ ...prev, [uid]: !prev[uid] }));
  }, []);

  const visibleL2 = useMemo(() => {
    if (collapsedIds[tree.uid]) return [];
    return tree.children;
  }, [tree, collapsedIds]);

  const visibleL3 = useMemo(() => {
    if (collapsedIds[tree.uid]) return [];
    const list: NormalizedTreeNode[] = [];
    tree.children.forEach((l2) => {
      if (!collapsedIds[l2.uid] && l2.children.length > 0) {
        list.push(...l2.children);
      }
    });
    return list;
  }, [tree, collapsedIds]);

  const hasAnyL3InTree = useMemo(
    () => tree.children.some((l2) => l2.children.length > 0),
    [tree]
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

    // Trace ancestors
    let curr: string | null = activeFocusId;
    while (curr && parentMap[curr]) {
      const p: string = parentMap[curr]!;
      set.add(p);
      curr = p;
    }

    // Trace descendants
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
    if (!containerRef.current) return;
    const containerEl = containerRef.current;
    const containerRect = containerEl.getBoundingClientRect();
    if (containerRect.width === 0 && containerRect.height === 0) return;

    setSvgSize({
      width: Math.max(containerEl.scrollWidth, containerRect.width),
      height: Math.max(containerEl.scrollHeight, containerRect.height),
    });

    const newEdges: typeof edges = [];
    const connectPair = (parentUid: string, childUid: string) => {
      const pEl = nodeRefs.current[parentUid];
      const cEl = nodeRefs.current[childUid];
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
        id: `${parentUid}->${childUid}`,
        from: parentUid,
        to: childUid,
        d,
        startX,
        startY,
        endX,
        endY,
      });
    };

    if (!collapsedIds[tree.uid]) {
      tree.children.forEach((l2) => {
        connectPair(tree.uid, l2.uid);
        if (!collapsedIds[l2.uid]) {
          l2.children.forEach((l3) => {
            connectPair(l2.uid, l3.uid);
          });
        }
      });
    }

    setEdges(newEdges);
  }, [tree, collapsedIds]);

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
  }, [calculateEdges, visibleL2.length, visibleL3.length]);

  const renderNodeCard = (node: NormalizedTreeNode) => {
    const hasVal =
      node.value !== null &&
      node.value !== undefined &&
      String(node.value).trim() !== '' &&
      String(node.value).trim() !== '-' &&
      String(node.value).trim() !== 'None';
    const hasChildren = node.children.length > 0;
    const isCollapsed = Boolean(collapsedIds[node.uid]);
    const isSelected = selectedId === node.uid;
    const isHighlighted = activeFocusId ? relatedIds.has(node.uid) : false;
    const isDimmed = activeFocusId ? !relatedIds.has(node.uid) : false;

    return (
      <div
        key={node.uid}
        data-testid={`tree-node-${node.level}`}
        ref={(el) => {
          nodeRefs.current[node.uid] = el;
        }}
        onClick={() => setSelectedId((prev) => (prev === node.uid ? null : node.uid))}
        onMouseEnter={() => setHoveredId(node.uid)}
        onMouseLeave={() => setHoveredId(null)}
        className={`relative rounded-xl bg-white p-3.5 transition-all duration-200 cursor-pointer select-none border ${
          isSelected
            ? 'border-indigo-600 ring-2 ring-indigo-500/20 shadow-md'
            : isHighlighted
            ? 'border-indigo-400 shadow-sm bg-indigo-50/15'
            : 'border-slate-200 hover:border-slate-300 shadow-2xs'
        } ${isDimmed ? 'opacity-40' : 'opacity-100'}`}
      >
        {/* Dòng 1: Cấp độ + Giá trị hoặc trạng thái nhóm + Nút đóng/mở nhánh */}
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono text-[10px] font-semibold">
            Cấp {node.level}
          </span>

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

        {/* Dòng 2: Tên chỉ tiêu */}
        <div className="text-xs font-bold text-slate-800 leading-snug">{node.name}</div>

        {/* Dòng 3: Đơn vị thực hiện (tối giản) */}
        <div className="text-[11px] text-slate-500 mt-1">
          Đơn vị: <span className="font-medium text-slate-700">{node.office_name}</span>
        </div>

        {/* Nút 1-Click Drill-Down: Tra cứu số liệu chi tiết của chỉ tiêu lá (REQ-Q04/Q01 -> REQ-Q02) */}
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
                  `Cho tôi biết số liệu chỉ tiêu ${node.name} thuộc nhóm ${tree.name} năm 2026?`
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
        {Object.values(collapsedIds).some(Boolean) && (
          <button
            type="button"
            onClick={() => setCollapsedIds({})}
            className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-700 px-2 py-0.5 rounded bg-indigo-50 border border-indigo-200 transition"
          >
            Mở rộng lại các nhánh
          </button>
        )}
      </div>

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
        className={`relative z-10 grid items-center gap-x-14 mb-3 ${
          hasAnyL3InTree
            ? 'grid-cols-[minmax(250px,280px)_minmax(260px,300px)_minmax(260px,310px)]'
            : 'grid-cols-[minmax(260px,320px)_minmax(280px,360px)]'
        }`}
      >
        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1">
          Cấp 1 • Nhóm chỉ tiêu gốc
        </div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1">
          Cấp 2 • Chỉ tiêu thành phần ({visibleL2.length})
        </div>
        {hasAnyL3InTree && (
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1">
            Cấp 3 • Chỉ tiêu chi tiết ({visibleL3.length})
          </div>
        )}
      </div>

      {/* Thân sơ đồ cây căn đỉnh (items-start), mỗi nhánh Cấp 2 nằm ngang hàng trực tiếp với cụm Cấp 3 của chính nó */}
      <div
        className={`relative z-10 grid items-start gap-x-14 ${
          hasAnyL3InTree
            ? 'grid-cols-[minmax(250px,280px)_1fr]'
            : 'grid-cols-[minmax(260px,320px)_minmax(280px,360px)]'
        }`}
      >
        {/* CỘT 1: CẤP 1 (Neo ở phía trên để luôn hiển thị ngay khi mở Modal) */}
        <div className="flex flex-col justify-start pt-1">
          {renderNodeCard(tree)}
        </div>

        {/* CỘT 2 & CỘT 3: Ghép theo từng cụm nhánh Cấp 2 -> Cấp 3 */}
        {visibleL2.length > 0 ? (
          <div className="flex flex-col space-y-4">
            {visibleL2.map((l2) => {
              const l3Children = collapsedIds[l2.uid] ? [] : l2.children;
              if (!hasAnyL3InTree) {
                return <div key={`row-${l2.uid}`}>{renderNodeCard(l2)}</div>;
              }
              return (
                <div
                  key={`row-${l2.uid}`}
                  className="grid grid-cols-[minmax(260px,300px)_minmax(260px,310px)] items-center gap-x-14"
                >
                  <div className="flex flex-col justify-center">
                    {renderNodeCard(l2)}
                  </div>
                  <div className="flex flex-col justify-center space-y-2.5">
                    {l3Children.map((l3) => renderNodeCard(l3))}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-xs text-slate-400 italic px-1 py-4">
            Đã thu gọn nhánh Cấp 2 (bấm +{tree.children.length} ở thẻ Cấp 1 để mở)
          </div>
        )}
      </div>

      {/* Thanh Inspector Panel Footer cố định dưới đáy Canvas */}
      <div
        data-testid="tree-inspector-footer"
        className="sticky bottom-0 z-20 mt-4 pt-3 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3 bg-slate-50/95 backdrop-blur-xs px-3.5 py-2.5 rounded-xl shadow-xs"
      >
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
                    `Cho tôi biết số liệu chỉ tiêu ${selectedNode.name} thuộc nhóm ${tree.name} năm 2026?`
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
            💡 Bấm trực tiếp <strong>🔍 Tra cứu số liệu</strong> trên từng chỉ tiêu lá hoặc bấm chọn một ô chỉ tiêu để xem chi tiết tại thanh Inspector này.
          </div>
        )}
      </div>
    </div>
  );
};

interface InteractiveCriteriaTreeModalProps {
  activeTreeNodes: any[];
  expandAllCounter: number;
  onExpandAll: () => void;
  onClose: () => void;
  onSelectChip?: (chip: string) => void;
}

const InteractiveCriteriaTreeModal: React.FC<InteractiveCriteriaTreeModalProps> = ({
  activeTreeNodes,
  expandAllCounter,
  onExpandAll,
  onClose,
  onSelectChip,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-4"
    >
      <div className="bg-white border border-slate-200 rounded-2xl max-w-6xl w-full max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 bg-white border-b border-slate-200 shrink-0">
          <div>
            <h3 className="text-sm font-bold text-slate-800">
              Sơ đồ cây phân cấp chỉ tiêu (Cấp 1 ➔ Cấp 2 ➔ Cấp 3)
            </h3>
            <p className="text-[11px] text-slate-500">
              Di chuột hoặc bấm vào nhánh để làm nổi bật đường dẫn • Bấm nút thu gọn/mở rộng trên từng nhánh cha
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onExpandAll}
              className="px-2.5 py-1 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium transition"
            >
              Mở rộng tất cả
            </button>
            <button
              type="button"
              onClick={onClose}
              title="Đóng cửa sổ (X)"
              aria-label="Đóng cửa sổ"
              className="w-8 h-8 rounded-lg bg-white hover:bg-rose-50 text-slate-500 hover:text-rose-600 border border-slate-200 flex items-center justify-center font-bold text-sm transition"
            >
              ✕
            </button>
          </div>
        </div>
        <div className="p-5 overflow-y-auto overflow-x-auto space-y-4 bg-white flex-1">
          {activeTreeNodes.map((rootNode: any, idx: number) => (
            <InteractiveCriteriaTreeCanvas
              key={rootNode.id || idx}
              rawRoot={rootNode}
              globalExpandSignal={expandAllCounter}
              onSelectChip={onSelectChip}
              onClose={onClose}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export const SmartTable: React.FC<SmartTableProps> = ({ tabularData, children, onSelectChip }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [copied, setCopied] = useState(false);
  const [activeTreeRootId, setActiveTreeRootId] = useState<string | null>(null);
  const [expandAllCounter, setExpandAllCounter] = useState(0);

  // Xác định cấu trúc cột và dòng
  const { columns, rows, title, treeModal } = useMemo(
    () => resolveSmartTableData(tabularData, children),
    [tabularData, children]
  );

  // Kiểm tra xem bảng hiện tại có phải là Bảng Danh Sách Nhiệm Vụ (REQ-Q03) hay không
  const isMissionListingTable = useMemo(() => {
    if (!columns || columns.length === 0) return false;
    const hasTreeModalData = Boolean(treeModal && Object.keys(treeModal).length > 0);
    if (hasTreeModalData) return false;

    const colKeys = columns.map((c) => String(c.key || '').toLowerCase().trim());
    const colLabels = columns.map((c) => String(c.label || '').toLowerCase().trim());

    // Loại trừ bảng chỉ tiêu số liệu (Fact) hoặc bảng cây chỉ tiêu Cấp 1 (REQ-Q01 / REQ-Q02 / REQ-Q04)
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

    // Loại trừ bảng tiến độ phê duyệt báo cáo (SC-5.1) hoặc bảng cán bộ phụ trách (SC-5.3 user_mission)
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

    const parseVnNum = (v: any): number => {
      const cleaned = cleanDisplayString(v).replace(/\s*\([^)]*\)\s*/g, '').trim();
      // Nếu định dạng phân tách hàng nghìn bằng dấu chấm kiểu Việt Nam (VD: 1.000, 12.500.000)
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

  // Nếu không phân tích được cột nào, render fallback có viền và style đầy đủ
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
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
            <TableIcon className="w-3.5 h-3.5" />
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

      {/* 2. Khung cuộn bảng dữ liệu gọn gàng, khoảng cách cột hợp lý dễ dò ngang */}
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
                                  `Hiển thị các chỉ tiêu cấp 1 của nhiệm vụ ${cleanVal} năm 2026?`
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
                  Không tìm thấy dòng số liệu nào khớp với từ khóa tìm kiếm.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 3. Pop-up Tree Modal Nền Trắng Tối Giản Tương Tác (PA 2.1: REQ-Q01 / SC-1.1 / REQ-Q04 / SC-4.1) */}
      {activeTreeRootId && (
        <InteractiveCriteriaTreeModal
          activeTreeNodes={activeTreeNodes}
          expandAllCounter={expandAllCounter}
          onExpandAll={() => setExpandAllCounter((c) => c + 1)}
          onClose={() => setActiveTreeRootId(null)}
          onSelectChip={onSelectChip}
        />
      )}
    </div>
  );
};
