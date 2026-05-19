import React from 'react';
import { MODULE_TYPES } from '../../../lib/constants';
import {
  MessageSquare, Bot, FileText, ArrowRightFromLine,
  GitBranch, Shuffle, Globe, BookOpen, GripVertical,
} from 'lucide-react';

const categoryOrder = ['Core', 'AI', 'Logic', 'Integration'];

const iconMap: Record<string, React.ReactNode> = {
  input:        <ArrowRightFromLine className="w-3.5 h-3.5" />,
  output:       <FileText className="w-3.5 h-3.5" />,
  agent:        <Bot className="w-3.5 h-3.5" />,
  prompt:       <MessageSquare className="w-3.5 h-3.5" />,
  conditional:  <GitBranch className="w-3.5 h-3.5" />,
  transform:    <Shuffle className="w-3.5 h-3.5" />,
  http_request: <Globe className="w-3.5 h-3.5" />,
  knowledge:    <BookOpen className="w-3.5 h-3.5" />,
};

const ModuleLibrary: React.FC = () => {
  type ModuleType = (typeof MODULE_TYPES)[number];
  const grouped = categoryOrder.reduce<Record<string, ModuleType[]>>((acc, category) => {
    const items = MODULE_TYPES.filter((m) => m.category.toLowerCase() === category.toLowerCase());
    if (items.length > 0) acc[category] = [...items];
    return acc;
  }, {});

  const onDragStart = (event: React.DragEvent<HTMLDivElement>, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      className="w-56 h-full overflow-y-auto flex flex-col"
      style={{
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 shrink-0"
        style={{ borderBottom: '1px solid var(--border-subtle)' }}
      >
        <h2 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
          Modules
        </h2>
        <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-disabled)' }}>
          Drag onto canvas
        </p>
      </div>

      {/* Module groups */}
      <div className="p-3 space-y-5 flex-1">
        {categoryOrder.map((category) => {
          const items = grouped[category];
          if (!items || items.length === 0) return null;

          return (
            <div key={category}>
              <h3
                className="text-[9px] font-extrabold uppercase tracking-widest mb-2 px-1"
                style={{ color: 'var(--text-disabled)' }}
              >
                {category}
              </h3>
              <div className="space-y-1">
                {items.map((mod) => (
                  <div
                    key={mod.type}
                    draggable
                    onDragStart={(e) => onDragStart(e, mod.type)}
                    className="flex items-center gap-2 px-2 py-2 rounded-lg cursor-grab active:cursor-grabbing transition-all group"
                    style={{
                      border: '1px solid var(--border-subtle)',
                      background: 'var(--bg-elevated)',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.background = 'var(--bg-overlay)';
                      e.currentTarget.style.borderColor = 'var(--border-default)';
                      e.currentTarget.style.transform = 'translateX(2px)';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.background = 'var(--bg-elevated)';
                      e.currentTarget.style.borderColor = 'var(--border-subtle)';
                      e.currentTarget.style.transform = 'none';
                    }}
                  >
                    <GripVertical className="w-2.5 h-2.5 flex-shrink-0 opacity-30 group-hover:opacity-60 transition-opacity" style={{ color: 'var(--text-muted)' }} />
                    <div
                      className="flex items-center justify-center w-6 h-6 rounded flex-shrink-0"
                      style={{ background: `${mod.color}20`, color: mod.color }}
                    >
                      {iconMap[mod.type] || <FileText className="w-3.5 h-3.5" />}
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold truncate" style={{ color: 'var(--text-secondary)' }}>
                        {mod.label}
                      </p>
                      <p className="text-[9px] truncate" style={{ color: 'var(--text-disabled)' }}>
                        {mod.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ModuleLibrary;
