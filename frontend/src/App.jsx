import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import DocumentChatPage from './pages/DocumentChatPage';
import GeneralChatPage from './pages/GeneralChatPage';
import SpreadsheetChatPage from './pages/SpreadsheetChatPage';
import PolicyChatPage from './pages/PolicyChatPage';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/dashboard" element={
            <ProtectedRoute><DashboardPage /></ProtectedRoute>
          } />
          <Route path="/chat/general" element={
            <ProtectedRoute><GeneralChatPage /></ProtectedRoute>
          } />
          <Route path="/chat/document" element={
            <ProtectedRoute><DocumentChatPage /></ProtectedRoute>
          } />
          <Route path="/chat/spreadsheet" element={
            <ProtectedRoute><SpreadsheetChatPage /></ProtectedRoute>
          } />
          <Route path="/chat/policy" element={
            <ProtectedRoute><PolicyChatPage /></ProtectedRoute>
          } />
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
