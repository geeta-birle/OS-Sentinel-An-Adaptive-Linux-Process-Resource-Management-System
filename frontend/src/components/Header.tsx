import React from 'react';

interface HeaderProps {
  appName: string;
  phase: string;
}

export const Header: React.FC<HeaderProps> = ({ appName, phase }) => {
  return (
    <header className="sentinel-header">
      <div className="header-branding">
        <div className="logo-badge">🛡️</div>
        <div>
          <h1 className="header-title">{appName}</h1>
          <p className="header-subtitle">Adaptive Linux Process & Resource Management System</p>
        </div>
      </div>
      <div className="phase-badge">
        <span className="badge-tag">{phase}</span>
      </div>
    </header>
  );
};
