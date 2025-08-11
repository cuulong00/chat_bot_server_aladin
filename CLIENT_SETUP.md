# Client Setup Instructions

## 📋 Tổng quan

Project này đã được cấu hình để chạy client React đầy đủ bên trong project LangGraph. Tất cả các thư mục client đã được thêm vào gitignore để không commit lên repository.

## 🚀 Cách chạy Client

### Option 1: Sử dụng script tự động
```bash
# Linux/Mac
./start-client.sh

# Windows
start-client.bat
```

### Option 2: Chạy manual
```bash
cd client
npm run dev
```

## 🔧 Cấu hình Environment

File `.env.local` đã được tạo tự động với cấu hình:
- **API URL**: `http://localhost:2024`
- **Assistant ID**: `fe096781-5601-53d2-b2f6-0d3403f7e9ca`
- **Streaming**: Enabled
- **Subgraphs**: Enabled

## 📁 Cấu trúc thư mục

```
chatbot/
├── client/                 # React client app (ignored by git)
│   ├── src/
│   ├── package.json
│   ├── .env.local         # Local environment config
│   └── .env.example       # Environment template
├── test-client/           # Simple test client (ignored by git)
├── react-streaming-test/  # React streaming test (ignored by git)
├── start-client.sh        # Linux/Mac start script
├── start-client.bat       # Windows start script
└── .gitignore            # Updated with client ignores
```

## 🔒 Git Ignore

Các thư mục và file sau đã được thêm vào `.gitignore`:
- `client/`
- `test-client/`
- `react-streaming-test/`
- `node_modules/`
- Các file build và cache của Node.js
- Environment files (.env.local, etc.)
- Start scripts

## 🛠️ Development Workflow

1. **Start LangGraph server**:
   ```bash
   python app.py
   ```

2. **Start client** (in another terminal):
   ```bash
   ./start-client.sh
   # hoặc
   start-client.bat
   ```

3. **Access applications**:
   - LangGraph API: `http://localhost:2024`
   - Client UI: `http://localhost:3000`

## 🔄 Streaming Configuration

Client đã được cấu hình để hỗ trợ streaming với subgraphs:
- `streamMode: ["values", "messages"]`
- `streamSubgraphs: true`
- `stream_subgraphs: true` (fallback)

## 🐛 Troubleshooting

### Port conflicts
- LangGraph: port 2024
- Client: port 3000

### Environment issues
- Check `.env.local` file exists
- Verify API_URL và ASSISTANT_ID

### Streaming issues
- Check console logs for streaming config
- Verify server is running on port 2024
