import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SmartTable, resolveSmartTableData } from '../SmartTable';
import { stripTenantContextPrefix } from '../../../lib/storage';
import { TabularData } from '../../../types/chat';

export function runGate5UnitTests() {
  // =========================================================================
  // TEST 1: Scenario A — Single message with 3 distinct Markdown tables + tabular_data (Table 1)
  // =========================================================================
  const table1Rows = Array.from({ length: 9 }, (_, i) => ({
    stt: i + 1,
    report_date: `2026-0${(i % 9) + 1}-28`,
    submitted_date: i < 7 ? `2026-0${(i % 9) + 1}-29` : 'Chưa nộp (NULL)',
    status_display: i < 7 ? 'Đã phê duyệt' : 'Bản nháp',
    created_by: 'admin_lamdong',
    office_name: 'Chi cục',
    mission_name: i < 7 ? 'Phát triển nông thôn' : 'Diêm nghiệp',
    criteria_count: 122,
    recorded_criteria_count: 60 + i,
  }));

  const table1TabularData: TabularData = {
    title: 'Kiểm toán tiến độ nộp & trạng thái phê duyệt báo cáo năm 2026',
    columns: [
      { key: 'stt', label: 'STT', align: 'center', data_type: 'number' },
      { key: 'report_date', label: 'Kỳ báo cáo (report_date)', align: 'center', data_type: 'text' },
      { key: 'submitted_date', label: 'Ngày nộp (submitted_date)', align: 'center', data_type: 'text' },
      { key: 'status_display', label: 'Trạng thái', align: 'center', data_type: 'badge' },
      { key: 'created_by', label: 'Người tạo', align: 'center', data_type: 'text' },
      { key: 'office_name', label: 'Đơn vị thực hiện', align: 'left', data_type: 'text' },
      { key: 'mission_name', label: 'Nhiệm vụ báo cáo', align: 'left', data_type: 'text' },
      { key: 'criteria_count', label: 'Tổng chỉ tiêu', align: 'center', data_type: 'number' },
      { key: 'recorded_criteria_count', label: 'Chỉ tiêu đã có số liệu', align: 'center', data_type: 'number' },
    ],
    rows: table1Rows,
    total_records: 9,
  };

  let mdTable1 =
    '| STT | Kỳ báo cáo (`report_date`) | Ngày nộp (`submitted_date`) | Trạng thái (`status`) | Người tạo (`created_by`) | Đơn vị thực hiện | Nhiệm vụ báo cáo | Tổng chỉ tiêu | Chỉ tiêu đã ghi nhận số liệu |\n' +
    '| :---: | :---: | :---: | :---: | :---: | :--- | :--- | :---: | :---: |\n';
  for (const r of table1Rows) {
    mdTable1 += `| ${r.stt} | **${r.report_date}** | ${r.submitted_date} | ${r.status_display} | \`${r.created_by}\` | ${r.office_name} | ${r.mission_name} | ${r.criteria_count} | **${r.recorded_criteria_count}** |\n`;
  }

  let mdTable2 =
    '| STT | Kỳ báo cáo nháp (`report_date`) | Mã chỉ tiêu (`code`) | Tên chỉ tiêu | Giá trị bản nháp (`value`) | Nhiệm vụ | Đơn vị |\n' +
    '| :---: | :---: | :---: | :--- | :---: | :--- | :--- |\n';
  for (let i = 1; i <= 14; i++) {
    mdTable2 += `| ${i} | **2026-09-22** | \`DN_DRAFT_${i}\` | **Chỉ tiêu nháp thứ ${i}** | **${i * 10}** | Diêm nghiệp | Chi cục |\n`;
  }

  let mdTable3 =
    '| STT | Mã chỉ tiêu (`code`) | Tên chỉ tiêu | Nhóm chỉ tiêu cha | Giá trị `approved` (Kỳ duyệt) | Giá trị `draft` (Kỳ nháp) | Chênh lệch (`Draft - Approved`) |\n' +
    '| :---: | :---: | :--- | :--- | :---: | :---: | :---: |\n';
  for (let i = 1; i <= 72; i++) {
    mdTable3 += `| ${i} | \`DIFF_CODE_${i}\` | **Chỉ tiêu đối chiếu ${i}** | Nhóm gốc ${i} | **100** *(2026-06-30)* | **150** *(2026-09-22)* | **\`+50\`** |\n`;
  }

  const fullMarkdown = [
    '### Bảng 1: Tổng hợp 9 kỳ báo cáo',
    mdTable1,
    '### Bảng 2: Chi tiết 14 chỉ tiêu bản nháp',
    mdTable2,
    '### Bảng 3: Đối chiếu 72 chỉ tiêu chênh lệch Draft vs Approved',
    mdTable3,
  ].join('\n\n');

  // Mô phỏng chính xác cách MessageItem.tsx render ReactMarkdown với cùng message.tabular_data truyền vào mọi bảng
  const renderedHtml = renderToStaticMarkup(
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ children }: any) => (
          <SmartTable tabularData={table1TabularData}>{children}</SmartTable>
        ),
      }}
    >
      {fullMarkdown}
    </ReactMarkdown>
  );

  // Phải có mặt cả 3 badge số lượng bản ghi của 3 bảng: "9 bản ghi", "14 bản ghi", "72 bản ghi"
  assert.ok(
    renderedHtml.includes('9 bản ghi'),
    'Table 1 must render 9 bản ghi'
  );
  assert.ok(
    renderedHtml.includes('14 bản ghi'),
    'Table 2 must render 14 bản ghi (not overwritten by Table 1)'
  );
  assert.ok(
    renderedHtml.includes('72 bản ghi'),
    'Table 3 must render 72 bản ghi (not overwritten by Table 1)'
  );

  // Kiểm tra các header và nội dung đặc trưng của cả 3 bảng đều xuất hiện
  assert.ok(
    renderedHtml.includes('Kiểm toán tiến độ nộp &amp; trạng thái phê duyệt báo cáo năm 2026'),
    'Table 1 must display its tabularData title'
  );
  assert.ok(
    renderedHtml.includes('Kỳ báo cáo nháp (report_date)') &&
      renderedHtml.includes('Chỉ tiêu nháp thứ 14'),
    'Table 2 must render its own headers and 14th row'
  );
  assert.ok(
    renderedHtml.includes('Chênh lệch (Draft - Approved)') &&
      renderedHtml.includes('Chỉ tiêu đối chiếu 72'),
    'Table 3 must render its own headers and 72nd row'
  );

  // Edge case: 2 bảng có cùng số cột (3 cột) và cùng số dòng (2 dòng) nhưng khác tên cột
  const sameShapeMd = [
    '| STT | Mã báo cáo | Trạng thái |',
    '| :---: | :---: | :---: |',
    '| 1 | BC_01 | Đã phê duyệt |',
    '| 2 | BC_02 | Bản nháp |',
    '',
    '| STT | Mã chỉ tiêu | Chênh lệch |',
    '| :---: | :---: | :---: |',
    '| 1 | CT_99 | +120 |',
    '| 2 | CT_100 | -45 |',
  ].join('\n');

  const sameShapeTabular: TabularData = {
    title: 'Bảng 1 cùng kích thước',
    columns: [
      { key: 'stt', label: 'STT', align: 'center', data_type: 'number' },
      { key: 'code', label: 'Mã báo cáo', align: 'center', data_type: 'text' },
      { key: 'status', label: 'Trạng thái', align: 'center', data_type: 'badge' },
    ],
    rows: [
      { stt: 1, code: 'BC_01', status: 'Đã phê duyệt' },
      { stt: 2, code: 'BC_02', status: 'Bản nháp' },
    ],
    total_records: 2,
  };

  const sameShapeHtml = renderToStaticMarkup(
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ children }: any) => (
          <SmartTable tabularData={sameShapeTabular}>{children}</SmartTable>
        ),
      }}
    >
      {sameShapeMd}
    </ReactMarkdown>
  );
  assert.ok(
    sameShapeHtml.includes('BC_01') && sameShapeHtml.includes('CT_99') && sameShapeHtml.includes('+120'),
    'Second table with same row/col count but different headers must not be overwritten by Table 1'
  );

  // Edge case: 2 bảng có CÙNG số cột, CÙNG số dòng VÀ CÙNG tên cột nhưng khác dữ liệu dòng đầu
  const identicalHeadersMd = [
    '| STT | Tên chỉ tiêu | Giá trị |',
    '| :---: | :--- | :---: |',
    '| 1 | Chỉ tiêu A1 | 100 |',
    '| 2 | Chỉ tiêu A2 | 200 |',
    '',
    '| STT | Tên chỉ tiêu | Giá trị |',
    '| :---: | :--- | :---: |',
    '| 1 | Chỉ tiêu B1 | 300 |',
    '| 2 | Chỉ tiêu B2 | 400 |',
  ].join('\n');

  const identicalHeadersTabular: TabularData = {
    title: 'Bảng chuyên biệt Nhóm A',
    columns: [
      { key: 'stt', label: 'STT', align: 'center', data_type: 'number' },
      { key: 'item', label: 'Tên chỉ tiêu', align: 'left', data_type: 'text' },
      { key: 'value', label: 'Giá trị', align: 'right', data_type: 'number' },
    ],
    rows: [
      { stt: 1, item: 'Chỉ tiêu A1', value: '100' },
      { stt: 2, item: 'Chỉ tiêu A2', value: '200' },
    ],
    total_records: 2,
  };

  const identicalHeadersHtml = renderToStaticMarkup(
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ children }: any) => (
          <SmartTable tabularData={identicalHeadersTabular}>{children}</SmartTable>
        ),
      }}
    >
      {identicalHeadersMd}
    </ReactMarkdown>
  );
  assert.ok(
    identicalHeadersHtml.includes('Chỉ tiêu A1') &&
      identicalHeadersHtml.includes('Chỉ tiêu B1') &&
      identicalHeadersHtml.split('Bảng chuyên biệt Nhóm A').length - 1 === 1,
    'Second table with identical headers and row count but different row data must not inherit Table 1 title'
  );

  // Edge case: Khi không có children (mdRows rỗng), SmartTable dùng trực tiếp tabularData
  const noChildrenResolved = resolveSmartTableData(sameShapeTabular, undefined);
  assert.equal(noChildrenResolved.rows.length, 2);
  assert.equal(noChildrenResolved.columns.length, 3);

  // Edge case: Bảng cây chỉ tiêu Cấp 1 (REQ-Q01 / REQ-Q04) bảo toàn tree_root_id và nút open-tree-modal-0
  const treeMd = [
    '| STT | Nhiệm vụ | Tên chỉ tiêu Cấp 1 | Loại cấu trúc Cấp 1 | Giá trị mới nhất | Đơn vị thực hiện |',
    '| :---: | :--- | :--- | :--- | :--- | :--- |',
    '| 1 | Phát triển nông thôn | **Số lượng cơ sở sản xuất** | Nhóm chỉ tiêu cha | **`- Xem chi tiết các chỉ tiêu con`** | Chi cục |',
  ].join('\n');
  const treeTabular: any = {
    title: 'Danh mục Chỉ tiêu Cấp 1 năm 2026',
    columns: [
      { key: 'stt', label: 'STT', align: 'center', data_type: 'number' },
      { key: 'mission', label: 'Nhiệm vụ', align: 'left', data_type: 'text' },
      { key: 'item', label: 'Tên chỉ tiêu Cấp 1', align: 'left', data_type: 'text' },
      { key: 'structure_type', label: 'Loại cấu trúc Cấp 1', align: 'left', data_type: 'text' },
      { key: 'value', label: 'Giá trị mới nhất', align: 'left', data_type: 'text' },
      { key: 'office', label: 'Đơn vị thực hiện', align: 'left', data_type: 'text' },
    ],
    rows: [
      {
        stt: 1,
        mission: 'Phát triển nông thôn',
        item: 'Số lượng cơ sở sản xuất',
        structure_type: 'Nhóm chỉ tiêu cha',
        value: '- Xem chi tiết các chỉ tiêu con',
        office: 'Chi cục',
        is_parent: true,
        tree_root_id: 'crit-root-01',
      },
    ],
    tree_modal: {
      'crit-root-01': { id: 'crit-root-01', name: 'Số lượng cơ sở sản xuất', children: [] },
    },
    total_records: 1,
  };
  const treeHtml = renderToStaticMarkup(
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ children }: any) => <SmartTable tabularData={treeTabular}>{children}</SmartTable>,
      }}
    >
      {treeMd}
    </ReactMarkdown>
  );
  assert.ok(
    treeHtml.includes('data-testid="open-tree-modal-0"'),
    'Tree parent row must render open-tree-modal-0 button'
  );

  // =========================================================================
  // TEST 2: Scenario B — Mission Drill-Down data-testid={`drilldown-mission-${rIdx}`}
  // =========================================================================
  const missionMd = [
    '| STT | Mã nhiệm vụ | Tên nhiệm vụ | Lĩnh vực | Đơn vị phụ trách |',
    '| :---: | :---: | :--- | :--- | :--- |',
    '| 1 | `NV_DN_01` | **Diêm nghiệp** | Nông nghiệp | Chi cục PTNT |',
    '| 2 | `NV_PTNT_02` | **Phát triển nông thôn** | Nông nghiệp | Chi cục PTNT |',
    '| 3 | `NV_CCHC_03` | **Cải cách hành chính** | Nội vụ | Văn phòng |',
  ].join('\n');

  const missionHtml = renderToStaticMarkup(
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ children }: any) => <SmartTable>{children}</SmartTable>,
      }}
    >
      {missionMd}
    </ReactMarkdown>
  );

  assert.ok(
    missionHtml.includes('data-testid="drilldown-mission-0"') &&
      missionHtml.includes('data-mission-name="Diêm nghiệp"'),
    'Row 0 mission button must have data-testid="drilldown-mission-0" and data-mission-name="Diêm nghiệp"'
  );
  assert.ok(
    missionHtml.includes('data-testid="drilldown-mission-1"') &&
      missionHtml.includes('data-mission-name="Phát triển nông thôn"'),
    'Row 1 mission button must have data-testid="drilldown-mission-1" and data-mission-name="Phát triển nông thôn"'
  );
  assert.ok(
    missionHtml.includes('data-testid="drilldown-mission-2"') &&
      missionHtml.includes('data-mission-name="Cải cách hành chính"'),
    'Row 2 mission button must have data-testid="drilldown-mission-2" and data-mission-name="Cải cách hành chính"'
  );

  // =========================================================================
  // TEST 3: Strip [tenant_code=...] from User Chat Bubble
  // =========================================================================
  const rawPrompt = '[tenant_code=68, level=0] Thống kê tiến độ nộp báo cáo năm 2026?';
  assert.equal(
    stripTenantContextPrefix(rawPrompt),
    'Thống kê tiến độ nộp báo cáo năm 2026?'
  );
  assert.equal(
    rawPrompt.replace(/^\[tenant_code=[^\]]+\]\s*/i, '').trim(),
    'Thống kê tiến độ nộp báo cáo năm 2026?'
  );

  console.log('ALL GATE 5 UNIT TESTS PASSED SUCCESSFULLY!');
}

runGate5UnitTests();
