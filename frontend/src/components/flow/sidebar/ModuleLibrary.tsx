import React from 'react';
import { MODULE_TYPES } from '../../../lib/constants';
import {
  MessageSquare,
  Bot,
  FileText,
  ArrowRightFromLine,
  GitBranch,
  Shuffle,
  Globe,
  BookOpen,
  GripVertical,
} from 'lucide-react';

const categoryOrder = ['Core', 'AI', 'Logic', 'Integration'];

const iconMap: Record<string, React.ReactNode> = {
  input: <ArrowRightFromLine className="w-4 h-4" />,
  output: <FileText className="w-4 h-4" />,
  agent: <Bot className="w-4 h-4" />,
  prompt: <MessageSquare className="w-4 h-4" />,
  conditional: <GitBranch className="w-4 h-4" />,
  transform: <Shuffle className="w-4 h-4" />,
  http_request: <Globe className="w-4 h-4" />,
  knowledge: <BookOpen className="w-4 h-4" />,
};

const ModuleLibrary: React.FC = () => {
  const grouped = categoryOrder.reduce<Record<string, typeof MODULE_TYPES[number][]>>(
    (acc, category) => {
      const items = MODULE_TYPES.filter(
        (m) => m.category.toLowerCase() === category.toLowerCase()
      );
      if (items.length > 0) {
        acc[category] = items;
      }
      return acc;
    },
    {}
  );

  const onDragStart = (
    event: React.DragEvent<HTMLDivElement>,
    nodeType: string
  ) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="w-64 bg-white dark:bg-ink-800 border-r border-ink-100/60 dark:border-ink-700/60 h-full overflow-y-auto shrink-0">
      <div className="p-4 border-b border-ink-100/60 dark:border-ink-700/60">
        <h2 className="font-body text-sm font-semibold text-ink-700 dark:text-cream-200">Modules</h2>
        <p className="font-body text-[11px] text-ink-300 dark:text-ink-400 mt-0.5">
          Drag modules onto the canvas
        </p>
      </div>

      <div className="p-3 space-y-5">
        {categoryOrder.map((category) => {
          const items = grouped[category];
          if (!items || items.length === 0) return null;

          return (
            <div key={category}>
              <h3 className="font-body text-[10px] font-semibold text-ink-300 dark:text-ink-400 uppercase tracking-wider mb-2 px-1">
                {category}
              </h3>
              <div className="space-y-1.5">
                {items.map((mod) => (
                  <div
                    key={mod.type}
                    draggable
                    onDragStart={(e) => onDragStart(e, mod.type)}
                    className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg border border-ink-100/40 dark:border-ink-700/40 bg-ink-50/30 dark:bg-ink-700/30 hover:bg-ink-50 dark:hover:bg-ink-700 hover:border-ink-100/60 dark:hover:border-ink-600 cursor-grab active:cursor-grabbing transition-all duration-150 group"
                  >
                    <GripVertical className="w-3.5 h-3.5 text-ink-200 group-hover:text-ink-300 flex-shrink-0 transition-colors" />
                    <div
                      className="flex items-center justify-center w-7 h-7 rounded-md flex-shrink-0"
                      style={{ backgroundColor: mod.color + '12', color: mod.color }}
                    >
                      {iconMap[mod.type] || <FileText className="w-4 h-4" />}
                    </div>
                    <div className="min-w-0">
                      <p className="font-body text-xs font-medium text-ink-600 dark:text-cream-200 truncate leading-tight">
                        {mod.label}
                      </p>
                      <p className="font-body text-[10px] text-ink-300 truncate leading-tight mt-0.5">
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
