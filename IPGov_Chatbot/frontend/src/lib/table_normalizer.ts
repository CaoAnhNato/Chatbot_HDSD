/**
 * Bộ tiền xử lý tự phục hồi cấu trúc Markdown Table (Self-Healing Table Normalizer)
 * Phục hồi các bảng Markdown bị mất dấu xuống dòng (\n) thành 1 dòng đơn (như Ảnh 3),
 * đồng thời bảo đảm khoảng cách phân tách hợp lệ cho parser GitHub Flavored Markdown (GFM).
 */

export function normalizeMarkdownTables(content: string): string {
  if (!content || typeof content !== 'string') return '';

  // 1. Kiểm tra xem văn bản có chứa cấu trúc phân cách cột của Markdown Table không
  // Dấu hiệu nhận biết: pattern |:---...| hoặc | --- |
  const delimiterRegex = /\|\s*:?-{2,}:?\s*\|/;
  if (!delimiterRegex.test(content)) {
    return content;
  }

  let raw = content;

  // 2. Tách phần văn bản dẫn nhập trước bảng nếu bị dính liền trên cùng 1 dòng với header bảng
  // Ví dụ: "Dưới đây là số liệu năm 2026: | STT | ..." -> "Dưới đây là số liệu năm 2026:\n\n| STT | ..."
  raw = raw.replace(/^([^|\n\r]+?)[ \t]*(\|[ \t]*[^\n|]+[ \t]*\|[ \t]*[^\n|]+[ \t]*\|)/gm, '$1\n\n$2');

  // 3. Tách các hàng bị dính liền trên cùng 1 dòng:
  // Ví dụ: "...| | :---: | ... | | 1 | ..." -> bẻ '| |' thành '|\n|'
  raw = raw.replace(/\|[ \t]+(\|(?:\s*:?-{2,}:?\s*\||[ \t]*[:\-\w*`\u00C0-\u1EF9]))/g, '|\n$1');

  // 4. Đảm bảo thẻ <details> không dính liền vào dòng cuối của bảng
  raw = raw.replace(/\|[ \t]*(<details[^>]*>)/gi, '|\n\n$1');

  // 5. Duyệt từng dòng để đảm bảo các khối bảng luôn có dòng trống (\n\n) trước và sau
  // Đây là điều kiện tiên quyết bắt buộc của chuẩn GFM / CommonMark để parser nhận diện thẻ <table>
  const lines = raw.split(/\r?\n/);
  const result: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    const isTableRow = trimmed.startsWith('|') && trimmed.endsWith('|');

    if (isTableRow) {
      // Nếu dòng trước đó không phải dòng bảng và không phải dòng trống -> chèn dòng trống
      const prevLine = result.length > 0 ? result[result.length - 1].trim() : '';
      if (prevLine !== '' && !(prevLine.startsWith('|') && prevLine.endsWith('|'))) {
        result.push('');
      }
      result.push(line);
    } else {
      // Nếu dòng này không phải dòng bảng, nhưng dòng trước đó là dòng bảng và dòng này không trống
      const prevLine = result.length > 0 ? result[result.length - 1].trim() : '';
      if (prevLine.startsWith('|') && prevLine.endsWith('|') && trimmed !== '') {
        result.push('');
      }
      result.push(line);
    }
  }

  return result.join('\n');
}

