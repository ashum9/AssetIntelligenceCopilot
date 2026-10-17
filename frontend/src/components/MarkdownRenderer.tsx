import React from 'react';

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  if (!content) return null;

  // Split lines and parse blocks cleanly
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let currentList: React.ReactNode[] = [];

  const flushList = () => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} className="my-2 space-y-1.5 pl-4 list-disc text-slate-700 text-xs md:text-sm">
          {currentList}
        </ul>
      );
      currentList = [];
    }
  };

  const renderInline = (text: string): React.ReactNode => {
    // Replace inline patterns
    // 1. Bold with code: **label:** `code` or **text**
    const parts: React.ReactNode[] = [];
    const regex = /(\*\*.*?\*\*|`.*?`)/g;
    let lastIdx = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIdx) {
        parts.push(text.substring(lastIdx, match.index));
      }
      const token = match[0];
      if (token.startsWith('**') && token.endsWith('**')) {
        parts.push(
          <strong key={match.index} className="font-semibold text-slate-900">
            {token.slice(2, -2)}
          </strong>
        );
      } else if (token.startsWith('`') && token.endsWith('`')) {
        parts.push(
          <code key={match.index} className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-sky-700 font-mono text-[11px] font-medium">
            {token.slice(1, -1)}
          </code>
        );
      }
      lastIdx = regex.lastIndex;
    }

    if (lastIdx < text.length) {
      parts.push(text.substring(lastIdx));
    }

    return parts.length > 0 ? parts : text;
  };

  lines.forEach((rawLine, idx) => {
    const line = rawLine.trim();

    if (!line) {
      flushList();
      return;
    }

    // Headings
    if (line.startsWith('### ')) {
      flushList();
      elements.push(
        <h4 key={idx} className="font-bold text-xs md:text-sm text-slate-900 uppercase tracking-wide mt-3 mb-1.5">
          {renderInline(line.slice(4))}
        </h4>
      );
    } else if (line.startsWith('## ')) {
      flushList();
      elements.push(
        <h3 key={idx} className="font-bold text-sm md:text-base text-slate-900 mt-3 mb-1.5">
          {renderInline(line.slice(3))}
        </h3>
      );
    } else if (line.startsWith('# ')) {
      flushList();
      elements.push(
        <h2 key={idx} className="font-bold text-base md:text-lg text-slate-900 mt-3 mb-2">
          {renderInline(line.slice(2))}
        </h2>
      );
    } else if (line.startsWith('- ') || line.startsWith('* ')) {
      // List items
      currentList.push(
        <li key={idx} className="leading-relaxed">
          {renderInline(line.slice(2))}
        </li>
      );
    } else {
      flushList();
      elements.push(
        <p key={idx} className="text-xs md:text-sm text-slate-700 leading-relaxed my-1.5">
          {renderInline(line)}
        </p>
      );
    }
  });

  flushList();

  return <div className="space-y-1">{elements}</div>;
};
