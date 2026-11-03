import './globals.css'
import type { ReactNode } from 'react'

export const metadata = {
  title: '视频工厂多 Agent 协作',
  description: 'Codex API powered multi-agent office for Baiqipu video factory',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
