const fs = require('fs');
const path = require('path');

// Đọc cổng từ tham số dòng lệnh hoặc biến môi trường
let port = process.env.PORT || '3000';
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  if ((args[i] === '-p' || args[i] === '--port') && args[i + 1]) {
    port = args[i + 1];
    break;
  }
}

// Đọc địa chỉ Backend API từ .env của IPGov_Chatbot/frontend
let backendUrl = 'http://localhost:8000/api/v1';
try {
  const envPath = path.join(__dirname, '..', '.env');
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf-8');
    const match = envContent.match(/NEXT_PUBLIC_API_URL=["']?([^"'\r\n]+)/);
    if (match && match[1]) {
      backendUrl = match[1];
    }
  }
} catch (e) {
  // Bỏ qua lỗi đọc file .env
}

console.log('\n' + '='.repeat(70));
console.log(`🚀 Đang kích hoạt IPGov_Chatbot (Frontend Web UI), port ${port}...`);
console.log('📌 Định danh hệ thống: IPGov_Chatbot (Kho Dữ Liệu Tỉnh - Độc lập với Chatbot_HDSD)');
console.log(`🌐 Địa chỉ giao diện:  http://localhost:${port}`);
console.log(`📡 Kết nối Backend:    ${backendUrl}`);
console.log('='.repeat(70) + '\n');
