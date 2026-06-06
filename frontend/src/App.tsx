import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import AppLayout from './components/Layout'
import Login from './pages/Login'
import Chat from './pages/Chat'
import Dashboard from './pages/Dashboard'
import UserDashboard from './pages/UserDashboard'
import Gateway from './pages/Gateway'
import Users from './pages/Users'
import Audit from './pages/Audit'
import Usage from './pages/Usage'
import ApiKeys from './pages/ApiKeys'
import Backup from './pages/Backup'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="chat" element={<Chat />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="my-usage" element={<UserDashboard />} />
        <Route path="gateway" element={<Gateway />} />
        <Route path="users" element={<Users />} />
        <Route path="audit" element={<Audit />} />
        <Route path="usage" element={<Usage />} />
        <Route path="api-keys" element={<ApiKeys />} />
        <Route path="backup" element={<Backup />} />
      </Route>
    </Routes>
  )
}

export default App
