import React, { useState } from 'react';
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from '@xyflow/react';
import { X } from 'lucide-react';
import useWorkflowStore from '../../../store/workflowStore';

const CustomEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
}) => {
  const [hovered, setHovered] = useState(false);
  const onEdgesChange = useWorkflowStore((s) => s.onEdgesChange);

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    onEdgesChange([{ id, type: 'remove' }]);
  };

  return (
    <>
      {/* Invisible wider path for hover detection */}
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={20}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      />
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          strokeWidth: hovered ? 2.5 : 1.5,
          stroke: hovered ? 'var(--accent-mid)' : 'rgba(99,102,241,0.4)',
          strokeDasharray: hovered ? undefined : '6 4',
          filter: hovered ? `drop-shadow(0 0 4px var(--accent-glow))` : 'none',
          transition: 'stroke 0.2s ease, stroke-width 0.2s ease, filter 0.2s ease',
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className="nodrag nopan"
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          {hovered && (
            <button
              className="flex items-center justify-center w-5 h-5 rounded-full text-white transition-all duration-150"
              style={{
                background: 'var(--status-error)',
                boxShadow: '0 2px 8px rgba(239,68,68,0.4)',
              }}
              onClick={handleDelete}
              title="Delete connection"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

export default CustomEdge;
