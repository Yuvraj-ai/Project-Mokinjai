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
  const grouped = categoryOrder.reduce<Record<string, typeof MODULE_TYPES>>(
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
    <div className="w-60 bg-white border-r border-gray-200 h-full overflow-y-auto">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-sm font-semibold text-gray-800">Modules</h2>
        <p className="text-[10px] text-gray-500 mt-0.5">
          Drag modules onto the canvas
        </p>
      </div>

      <div className="p-3 space-y-4">
        {categoryOrder.map((category) => {
          const items = grouped[category];
          if (!items || items.length === 0) return null;

          return (
            <div key={category}>
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2 px-1">
                {category}
              </h3>
              <div className="space-y-1.5">
                {items.map((mod) => (
                  <div
                    key={mod.type}
                    draggable
                    onDragStart={(e) => onDragStart(e, mod.type)}
                    className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg border border-gray-100 bg-gray-50 hover:bg-gray-100 hover:border-gray-200 cursor-grab active:cursor-grabbing transition-colors group"
                  >
                    <GripVertical className="w-3 h-3 text-gray-300 group-hover:text-gray-400 flex-shrink-0" />
                    <div
                      className="flex items-center justify-center w-7 h-7 rounded-md flex-shrink-0"
                      style={{ backgroundColor: mod.color + '20', color: mod.color }}
                    >
                      {iconMap[mod.type] || <FileText className="w-4 h-4" />}
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-gray-700 truncate">
                        {mod.label}
                      </p>
                      <p className="text-[10px] text-gray-400 truncate">
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
