import { createContext, useContext, useState, useEffect } from 'react';
import api from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(localStorage.getItem('token'));
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (token) {
            api.get('/auth/me')
                .then(res => {
                    setUser(res.data);
                    setLoading(false);
                })
                .catch(() => {
                    localStorage.removeItem('token');
                    localStorage.removeItem('user');
                    setToken(null);
                    setUser(null);
                    setLoading(false);
                });
        } else {
            setLoading(false);
        }
    }, [token]);

    const login = async (username, password) => {
        const res = await api.post('/auth/login', { username, password });
        const { token: newToken, user_id, username: uname } = res.data;
        localStorage.setItem('token', newToken);
        localStorage.setItem('user', JSON.stringify({ id: user_id, username: uname }));
        setToken(newToken);
        setUser({ id: user_id, username: uname });
        return res.data;
    };

    const register = async (username, password) => {
        const res = await api.post('/auth/register', { username, password });
        const { token: newToken, user_id, username: uname } = res.data;
        localStorage.setItem('token', newToken);
        localStorage.setItem('user', JSON.stringify({ id: user_id, username: uname }));
        setToken(newToken);
        setUser({ id: user_id, username: uname });
        return res.data;
    };

    const logout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        setToken(null);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
}
