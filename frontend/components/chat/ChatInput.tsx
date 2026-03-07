"use client";

import { useRef, useEffect } from "react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
}

export default function ChatInput({ value, onChange, onSubmit, disabled }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const composingRef = useRef(false);

  // Auto-resize textarea (1–6 rows)
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const lineHeight = 22;
    const minH = lineHeight;
    const maxH = lineHeight * 6;
    el.style.height = `${Math.min(Math.max(el.scrollHeight, minH), maxH)}px`;
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Do not submit while IME composition is active (Japanese/Chinese/Korean input)
    if (e.key === "Enter" && !e.shiftKey && !composingRef.current) {
      e.preventDefault();
      if (value.trim() && !disabled) onSubmit();
    }
  };

  return (
    <div className="px-6 pb-4">
      <div
        className="flex items-end gap-2 px-4 py-3 rounded-xl"
        style={{ background: "#F9FAFB", border: "1px solid #E5E7EB" }}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => { composingRef.current = true; }}
          onCompositionEnd={() => { composingRef.current = false; }}
          disabled={disabled}
          placeholder="Ask a legal question (JP / US)... Press Enter to send, Shift+Enter for newline"
          rows={1}
          className="flex-1 bg-transparent resize-none outline-none text-[14px] text-[#111827] placeholder-[#9CA3AF] leading-[22px]"
          style={{ fontFamily: "var(--font-ibm-plex-sans)" }}
        />
        <button
          onClick={() => value.trim() && !disabled && onSubmit()}
          disabled={!value.trim() || disabled}
          className="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-white text-lg transition-colors"
          style={{
            background: value.trim() && !disabled ? "#2D4FD6" : "#E5E7EB",
            color: value.trim() && !disabled ? "white" : "#9CA3AF",
          }}
          aria-label="Send message"
        >
          ↑
        </button>
      </div>
    </div>
  );
}
