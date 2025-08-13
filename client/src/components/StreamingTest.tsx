'use client';

import { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function StreamingTest({ apiUrl, assistantId }: { apiUrl: string; assistantId: string }) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<any[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!input.trim() || isStreaming) return;
    setIsStreaming(true);
    setStreamingContent('');

    let threadId = '';
    try {
      threadId = await createThread(apiUrl);
    } catch (err: any) {
      setError('Không tạo được thread: ' + (err?.message || 'Unknown error'));
      setIsStreaming(false);
      return;
    }
    const humanMessage = {
      id: Date.now().toString(),
      type: 'human',
      content: input.trim(),
      timestamp: new Date()
    };
    setMessages((prev) => [...prev, humanMessage]);

    // Streaming logic giống test-client
    const runData = {
      assistant_id: assistantId,
      input: {
        messages: [{
          type: 'human',
          content: humanMessage.content,
          id: humanMessage.id
        }]
      },
      stream_mode: ['values', 'messages'],
      stream_subgraphs: true
    };

    let response: Response;
    try {
      response = await fetch(`${apiUrl}/threads/${threadId}/runs/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify(runData)
      });
    } catch (err: any) {
      setError('Không gửi được request streaming: ' + (err?.message || 'Unknown error'));
      setIsStreaming(false);
      return;
    }

    if (!response.ok) {
      setError('Streaming response lỗi: ' + response.status + ' - ' + response.statusText);
      setIsStreaming(false);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      setError('Không lấy được reader từ response');
      setIsStreaming(false);
      return;
    }
    const decoder = new TextDecoder();
    let buffer = '';
    let accumulatedContent = '';
    let gotData = false;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          // Bỏ qua heartbeat messages
          if (line.trim() === ': heartbeat' || line.trim() === '') {
            continue;
          }
          
          if (line.startsWith('data: ')) {
            try {
              const dataStr = line.slice(6);
              if (!dataStr.trim()) continue; // Bỏ qua data trống
              
              const data = JSON.parse(dataStr);
              gotData = true;
              
              // Xử lý định dạng LangGraph streaming
              if (Array.isArray(data)) {
                for (const item of data) {
                  // Kiểm tra AIMessageChunk với content
                  if (item.type === 'AIMessageChunk' && item.content) {
                    accumulatedContent += item.content;
                    setStreamingContent(accumulatedContent);
                    // Chỉ log mỗi 5 tokens để tránh spam
                    if (accumulatedContent.length % 5 === 0) {
                      console.log('✅ Streaming progress:', accumulatedContent.length + ' chars');
                    }
                  }
                  // Kiểm tra AIMessage hoàn chỉnh
                  else if (item.type === 'ai' && typeof item.content === 'string') {
                    if (item.content.length > accumulatedContent.length) {
                      accumulatedContent = item.content;
                      setStreamingContent(accumulatedContent);
                      console.log('✅ Updated full content:', accumulatedContent.length + ' chars');
                    }
                  }
                }
              }
              // Xử lý event-based streaming
              else if (data.event === 'messages/partial') {
                if (data.data && Array.isArray(data.data)) {
                  for (const item of data.data) {
                    if (item.type === 'ai' && typeof item.content === 'string') {
                      if (item.content.length > accumulatedContent.length) {
                        accumulatedContent = item.content;
                        setStreamingContent(accumulatedContent);
                      }
                    }
                  }
                }
              }
              else if (data.event === 'on_chat_model_stream') {
                if (data.data && data.data.chunk && data.data.chunk.content) {
                  accumulatedContent += data.data.chunk.content;
                  setStreamingContent(accumulatedContent);
                }
              }
            } catch (e) {
              // Bỏ qua lỗi JSON parse cho heartbeat và metadata
              if (line.includes('heartbeat') || line.includes('event:')) {
                continue;
              }
              console.log('❌ JSON parse error:', line.substring(0, 100));
            }
          }
          // Xử lý event lines riêng biệt
          else if (line.startsWith('event: ')) {
            const eventType = line.slice(7);
            console.log('📡 Event:', eventType);
          }
        }
      }
    } catch (err: any) {
      setError('Lỗi khi đọc streaming: ' + (err?.message || 'Unknown error'));
      setIsStreaming(false);
      return;
    }

    if (!gotData) {
      setError('Không nhận được dữ liệu streaming từ server.');
    }

    if (accumulatedContent) {
      const aiMessage = {
        id: Date.now().toString(),
        type: 'ai',
        content: accumulatedContent,
        timestamp: new Date()
      };
      setMessages((prev) => [...prev, aiMessage]);
    }
    setIsStreaming(false);
    setStreamingContent('');
  };

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>StreamingTest (No SDK, pure fetch)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {error && (
              <div className="bg-red-100 text-red-700 p-3 rounded-lg border border-red-300 mb-2">
                <strong>Lỗi streaming:</strong> {error}
              </div>
            )}
            <div className="space-y-4 min-h-[400px] max-h-[600px] overflow-y-auto border rounded-lg p-4">
              {messages.map((message) => (
                <div key={message.id} className={`flex ${message.type === 'human' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[70%] p-3 rounded-lg ${message.type === 'human' ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-800'}`}>
                    <div className="whitespace-pre-wrap">{message.content}</div>
                    <div className="text-xs opacity-70 mt-1">{message.timestamp.toLocaleTimeString()}</div>
                  </div>
                </div>
              ))}
              {isStreaming && streamingContent && (
                <div className="flex justify-start">
                  <div className="max-w-[70%] p-3 rounded-lg bg-gray-100 text-gray-800 border-l-4 border-blue-500">
                    <div className="whitespace-pre-wrap">{streamingContent}</div>
                    <div className="text-xs opacity-70 mt-1 flex items-center gap-1">
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                      Streaming...
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            <form onSubmit={handleSubmit} className="flex gap-2">
              <Input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type your message..." disabled={isStreaming} className="flex-1" />
              <Button type="submit" disabled={!input.trim() || isStreaming} size="icon">Send</Button>
            </form>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

async function createThread(apiUrl: string): Promise<string> {
  const response = await fetch(`${apiUrl}/threads`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ metadata: { source: 'streaming_test' } })
  });
  if (!response.ok) throw new Error('Failed to create thread');
  const data = await response.json();
  return data.thread_id;
}
