import React from 'react';
import { Handle, Position } from '@xyflow/react';

interface BaseNodeProps {
  children: React.ReactNode;
  label: string;
  accentColor: string;
  icon?: React.ReactNode;
  selected?: boolean;
}

const BaseNode: React.FC<BaseNodeProps> = ({ children, label, accentColor, icon, selected }) => {
  return (
    <div
      className="node-card"
      style={
        {
          '--node-accent': accentColor,
          boxShadow: selected
            ? `0 0 0 2px ${accentColor}40, var(--shadow-md)`
            : 'var(--shadow-md)',
          borderColor: selected ? `${accentColor}60` : undefined,
        } as React.CSSProperties
      }
    >
      {/* Input handle — left */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: 'var(--text-muted)',
          border: '2px solid var(--bg-elevated)',
          width: 10,
          height: 10,
          borderRadius: '50%',
        }}
      />

      {/* Header */}
      <div className="node-header">
        {icon ? (
          <div
            className="flex items-center justify-center w-5 h-5 rounded flex-shrink-0"
            style={{ background: `${accentColor}20`, color: accentColor }}
          >
            {icon}
          </div>
        ) : (
          <div
            className="node-dot"
            style={{ background: accentColor }}
          />
        )}
        <span
          className="node-label flex-1 truncate"
          style={{ color: accentColor }}
        >
          {label}
        </span>
      </div>

      {/* Body */}
      <div className="node-body">{children}</div>

      {/* Output handle — right */}
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: accentColor,
          border: '2px solid var(--bg-elevated)',
          width: 10,
          height: 10,
          borderRadius: '50%',
        }}
      />
    </div>
  );
};

export default BaseNode;
