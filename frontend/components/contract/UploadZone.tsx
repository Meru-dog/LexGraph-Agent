"use client";

import { useRef, useState } from "react";

interface Props {
  onFile: (file: File) => void;
  disabled?: boolean;
}

export default function UploadZone({ onFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFile(file);
  };

  return (
    <div
      className="rounded-[10px] px-5 py-9 flex flex-col items-center justify-center cursor-pointer transition-all text-center"
      style={{
        border: `2px dashed ${dragOver ? "#2D4FD6" : "#D1D5DB"}`,
        background: dragOver ? "#F5F7FF" : "#FFFFFF",
      }}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
    >
      <div className="text-3xl mb-2">📄</div>
      <p className="text-[13px] font-medium text-[#374151]">Drop contract here</p>
      <p className="text-[11px] text-[#9CA3AF] mt-1">PDF, DOCX, TXT · Max 50MB</p>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.txt,.html"
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />
    </div>
  );
}
