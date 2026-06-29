import { useState } from 'react';
import { Landmark, Lock, User } from 'lucide-react';
import { useAuth } from '../../context/AuthContext.jsx';
import Button from '../ui/Button.jsx';

export default function LoginView() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login, loginError } = useAuth();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    await login(username, password);
    setIsSubmitting(false);
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-logo">
          <Landmark size={40} />
        </div>

        <h1 className="login-title">Museum Control</h1>
        <p className="login-subtitle">Prihláste sa pre prístup k ovládaniu</p>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="input-group">
            <User size={18} className="input-icon" />
            <input
              type="text"
              placeholder="Používateľské meno"
              className="login-input"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
            />
          </div>

          <div className="input-group">
            <Lock size={18} className="input-icon" />
            <input
              type="password"
              placeholder="Heslo"
              className="login-input"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </div>

          <Button type="submit" isLoading={isSubmitting} size="large" className="login-submit-btn">
            Prihlásiť sa
          </Button>

          {loginError && (
            <div className="login-error" role="alert" aria-live="polite">
              {loginError}
            </div>
          )}
        </form>

        <div className="login-footer">v1.0.0 • Museum System</div>
      </div>
    </div>
  );
}