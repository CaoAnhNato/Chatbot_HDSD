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

function normalizeTreeData(rawRoot: any): NormalizedTreeNode {
  const rootUid = String(rawRoot?.id || rawRoot?.code || `l1-${rawRoot?.name || 'root'}`);
  const rawL2: any[] = Array.isArray(rawRoot?.children) ? rawRoot.children : [];

  const l2Nodes: NormalizedTreeNode[] = rawL2.map((c2: any, idx2: number) => {
    const l2Uid = String(c2?.id || c2?.code || `${rootUid}-l2-${idx2}`);
    const rawL3: any[] = Array.isArray(c2?.children) ? c2.children : [];
    const l3Nodes: NormalizedTreeNode[] = rawL3.map((c3: any, idx3: number) => ({
      uid: String(c3?.id || c3?.code || `${l2Uid}-l3-${idx3}`),
      parentId: l2Uid,
      level: 3,
      name: String(c3?.name || 'Chỉ tiêu Cấp 3'),
      value: c3?.value,
      office_name: String(c3?.office_name || c2?.office_name || rawRoot?.office_name || 'Cấp tỉnh'),
      mission_name: String(c3?.mission_name || c2?.mission_name || rawRoot?.mission_name || ''),
      children: [],
    }));
    return {
      uid: l2Uid,
      parentId: rootUid,
      level: 2,
      name: String(c2?.name || 'Chỉ tiêu Cấp 2'),
      value: c2?.value,
      office_name: String(c2?.office_name || rawRoot?.office_name || 'Cấp tỉnh'),
      mission_name: String(c2?.mission_name || rawRoot?.mission_name || ''),
      children: l3Nodes,
    };
  });

  return {
    uid: rootUid,
    parentId: null,
    level: 1,
    name: String(rawRoot?.name || 'Nhóm chỉ tiêu Cấp 1'),
    value: rawRoot?.value,
    office_name: String(rawRoot?.office_name || 'Cấp tỉnh'),
    mission_name: String(rawRoot?.mission_name || ''),
    children: l2Nodes,
  };
}

const InteractiveCriteriaTreeCanvas: React.FC<{
  rawRoot: any;
  globalExpandSignal?: number;
}> = ({ rawRoot, globalExpandSignal }) => {
  const tree = useMemo(() => normalizeTreeData(rawRoot), [rawRoot]);
  const [collapsedIds, setCollapsedIds] = useState<Record<string, boolean>>({});
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
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
    </div>
  );
};

export const SmartTable: React.FC<SmartTableProps> = ({ tabularData, children }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [copied, setCopied] = useState(false);
  const [activeTreeRootId, setActiveTreeRootId] = useState<string | null>(null);
  const [expandAllCounter, setExpandAllCounter] = useState(0);

  // Xác định cấu trúc cột và dòng
  const { columns, rows, title, treeModal } = useMemo(() => {
    if (tabularData && tabularData.columns && tabularData.columns.length > 0) {
      return {
        columns: tabularData.columns,
        rows: tabularData.rows || [],
        title: tabularData.title,
        treeModal: (tabularData as any).tree_modal || {},
      };
    }
    const parsed = parseTableFromChildren(children);
    return {
      columns: parsed.columns,
      rows: parsed.rows,
      title: undefined,
      treeModal: {},
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
    const mapObj =
      treeModal && Object.keys(treeModal).length > 0
        ? treeModal
        : (tabularData as any)?.trees_by_root_id || {};
    if (mapObj && mapObj[activeTreeRootId]) {
      return [mapObj[activeTreeRootId]];
    }
    const vals: any[] = Object.values(mapObj || {});
    const byName = vals.filter(
      (n) =>
        n &&
        String(n.name || '')
          .trim()
          .toLowerCase() === String(activeTreeRootId).trim().toLowerCase()
    );
    if (byName.length > 0) return byName;
    return vals.length > 0 ? vals : [];
  }, [activeTreeRootId, treeModal, tabularData]);

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
              sortedRows.map((row, rIdx) => (
                <tr
                  key={`r-${rIdx}`}
                  className="odd:bg-white even:bg-slate-50/50 hover:bg-indigo-50/40 transition-colors duration-150 divide-x divide-slate-100"
                >
                  {columns.map((col) => {
                    const cellVal = row[col.key];
                    const cleanVal = String(cellVal ?? '').replace(/^\*\*|\*\*$/g, '').trim();
                    const isTreeTrigger =
                      cleanVal.includes('Xem chi tiết các chỉ tiêu con') ||
                      cleanVal.includes('Xem chi tiết con');
                    const isStt = col.key === 'stt' || col.label.toUpperCase() === 'STT';
                    return (
                      <td
                        key={`c-${col.key}`}
                        className={`py-2 px-3 align-middle ${
                          isStt
                            ? 'text-center w-12 whitespace-nowrap'
                            : 'text-left max-w-[280px] break-words'
                        }`}
                      >
                        {isTreeTrigger ? (
                          <button
                            type="button"
                            onClick={() => setActiveTreeRootId(row.tree_root_id || 'ALL')}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-xs font-semibold transition cursor-pointer whitespace-nowrap"
                            title="Bấm để mở sơ đồ cây phân cấp chỉ tiêu con"
                          >
                            <span>🌳 - Xem chi tiết các chỉ tiêu con</span>
                          </button>
                        ) : (
                          renderCellContent(cellVal, col)
                        )}
                      </td>
                    );
                  })}
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

      {/* 3. Pop-up Tree Modal Nền Trắng Tối Giản Tương Tác (PA 2.1: REQ-Q01 / SC-1.1 / REQ-Q04 / SC-4.1) */}
      {activeTreeRootId && (
        <div
          onClick={(e) => {
            if (e.target === e.currentTarget) setActiveTreeRootId(null);
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
                  onClick={() => setExpandAllCounter((c) => c + 1)}
                  className="px-2.5 py-1 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium transition"
                >
                  Mở rộng tất cả
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTreeRootId(null)}
                  title="Đóng cửa sổ (X)"
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
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
