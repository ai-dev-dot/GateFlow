import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to="/chat" replace />} />
      {/* Other routes will be added in Task 5 */}
    </Routes>
  )
}

export default App
