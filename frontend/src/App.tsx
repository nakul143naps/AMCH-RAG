import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { UserAssistant } from './pages/UserAssistant'
import { AdminCockpit } from './pages/AdminCockpit'

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public-facing pure Assistant (Safe for Public GitHub / Cloud Deployment) */}
        <Route path="/" element={<UserAssistant />} />

        {/* Dedicated Operations & Telemetry Cockpit for Mr. Admin */}
        <Route path="/admin" element={<AdminCockpit />} />

        {/* Fallback to user assistant */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
