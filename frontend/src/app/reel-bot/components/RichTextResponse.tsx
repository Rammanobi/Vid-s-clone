"use client"

import React from "react"
import { cn } from "@/lib/utils"

interface RichTextResponseProps {
  content: string
}

export function RichTextResponse({ content }: RichTextResponseProps) {
  const parseContent = (text: string) => {
    // Split by lines and process
    const lines = text.split("\n")
    const elements: React.ReactNode[] = []
    let currentList: string[] = []
    let listType: "bullet" | "number" | null = null

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim()

      // Handle headings (# ## ###)
      if (line.startsWith("###")) {
        if (currentList.length) {
          elements.push(renderList(currentList, listType))
          currentList = []
          listType = null
        }
        elements.push(
          <h3 key={`h3-${i}`} className="text-base font-bold text-amber-400 mt-4 mb-2">
            {line.replace(/^#+\s?/, "")}
          </h3>
        )
      } else if (line.startsWith("##")) {
        if (currentList.length) {
          elements.push(renderList(currentList, listType))
          currentList = []
          listType = null
        }
        elements.push(
          <h2 key={`h2-${i}`} className="text-lg font-bold text-amber-300 mt-4 mb-2">
            {line.replace(/^#+\s?/, "")}
          </h2>
        )
      } else if (line.startsWith("#")) {
        if (currentList.length) {
          elements.push(renderList(currentList, listType))
          currentList = []
          listType = null
        }
        elements.push(
          <h1 key={`h1-${i}`} className="text-xl font-bold text-amber-200 mt-4 mb-2">
            {line.replace(/^#+\s?/, "")}
          </h1>
        )
      }
      // Handle lists
      else if (line.startsWith("-") || line.startsWith("•")) {
        if (listType === "number") {
          elements.push(renderList(currentList, listType))
          currentList = []
        }
        listType = "bullet"
        currentList.push(line.replace(/^[-•]\s?/, ""))
      } else if (line.match(/^\d+\./)) {
        if (listType === "bullet") {
          elements.push(renderList(currentList, listType))
          currentList = []
        }
        listType = "number"
        currentList.push(line.replace(/^\d+\.\s?/, ""))
      }
      // Handle code blocks
      else if (line.startsWith("```")) {
        if (currentList.length) {
          elements.push(renderList(currentList, listType))
          currentList = []
          listType = null
        }
        const codeContent = lines
          .slice(i + 1)
          .join("\n")
          .split("```")[0]
        elements.push(
          <pre key={`code-${i}`} className="bg-black/50 border border-amber-600/20 rounded-lg p-4 my-3 overflow-x-auto text-xs font-mono text-amber-100">
            {codeContent.trim()}
          </pre>
        )
        i += codeContent.split("\n").length + 1
      }
      // Handle blockquotes
      else if (line.startsWith(">")) {
        if (currentList.length) {
          elements.push(renderList(currentList, listType))
          currentList = []
          listType = null
        }
        elements.push(
          <blockquote key={`quote-${i}`} className="border-l-4 border-amber-600/50 pl-4 py-2 my-2 italic text-foreground/70">
            {line.replace(/^>\s?/, "")}
          </blockquote>
        )
      }
      // Handle markdown tables: a "| a | b |" row followed by a
      // "|---|---|" separator row starts a table; consume every following
      // "|"-row as data. Without this, table rows fell through to the plain
      // "line" branch below - shown as raw "| 156.59 | 190.96 |" text in one
      // overflowing paragraph instead of a table.
      else if (line.startsWith("|") && lines[i + 1]?.trim().match(/^\|[\s:-]+\|/)) {
        if (currentList.length) {
          elements.push(renderList(currentList, listType))
          currentList = []
          listType = null
        }
        const parseRow = (row: string) =>
          row
            .trim()
            .replace(/^\||\|$/g, "")
            .split("|")
            .map((cell) => cell.trim())

        const header = parseRow(line)
        let j = i + 2 // skip header + separator row
        const bodyRows: string[][] = []
        while (j < lines.length && lines[j].trim().startsWith("|")) {
          bodyRows.push(parseRow(lines[j]))
          j++
        }

        elements.push(
          <div key={`table-${i}`} className="my-3 overflow-x-auto rounded-lg border border-amber-600/20">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-amber-600/10">
                  {header.map((cell, idx) => (
                    <th
                      key={idx}
                      className="px-3 py-2 text-left font-semibold text-amber-300 border-b border-amber-600/20 whitespace-nowrap"
                    >
                      {renderInlineFormatting(cell)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bodyRows.map((row, rIdx) => (
                  <tr key={rIdx} className="border-b border-border/20 last:border-0">
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="px-3 py-2 whitespace-nowrap">
                        {renderInlineFormatting(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
        i = j - 1
      }
      // Regular text with inline formatting
      else if (line) {
        if (currentList.length) {
          elements.push(renderList(currentList, listType))
          currentList = []
          listType = null
        }
        elements.push(
          <p key={`p-${i}`} className="text-base leading-relaxed mb-2">
            {renderInlineFormatting(line)}
          </p>
        )
      }
      // Empty lines
      else {
        if (currentList.length) {
          elements.push(renderList(currentList, listType))
          currentList = []
          listType = null
        }
      }
    }

    // Flush remaining list
    if (currentList.length) {
      elements.push(renderList(currentList, listType))
    }

    return elements
  }

  const renderList = (items: string[], type: "bullet" | "number" | null) => {
    if (type === "bullet") {
      return (
        <ul key={`list-${Math.random()}`} className="space-y-2 my-3 ml-4">
          {items.map((item, idx) => (
            <li key={idx} className="flex gap-2">
              <span className="text-amber-400 flex-shrink-0">•</span>
              <span className="text-base">{renderInlineFormatting(item)}</span>
            </li>
          ))}
        </ul>
      )
    }

    return (
      <ol key={`list-${Math.random()}`} className="space-y-2 my-3 ml-4">
        {items.map((item, idx) => (
          <li key={idx} className="flex gap-2">
            <span className="text-amber-400 flex-shrink-0 font-semibold">{idx + 1}.</span>
            <span className="text-base">{renderInlineFormatting(item)}</span>
          </li>
        ))}
      </ol>
    )
  }

  const renderInlineFormatting = (text: string) => {
    const parts: React.ReactNode[] = []
    let lastIndex = 0

    // Pattern for **bold**, *italic*, and `code`
    const pattern = /\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|(\d+(?:,\d+)*%?|\d+(?:,\d+)* (?:views?|likes?|comments?|shares?|reels?|reel))/gi

    let match
    const regex = new RegExp(pattern)

    while ((match = regex.exec(text)) !== null) {
      // Add text before match
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index))
      }

      if (match[1]) {
        // Bold
        parts.push(
          <strong key={`bold-${match.index}`} className="font-bold text-amber-300">
            {match[1]}
          </strong>
        )
      } else if (match[2]) {
        // Italic
        parts.push(
          <em key={`italic-${match.index}`} className="italic text-foreground/80">
            {match[2]}
          </em>
        )
      } else if (match[3]) {
        // Inline code
        parts.push(
          <code key={`code-${match.index}`} className="bg-black/30 px-2 py-1 rounded text-amber-100 text-xs font-mono">
            {match[3]}
          </code>
        )
      } else if (match[4]) {
        // Numbers/stats
        parts.push(
          <span key={`stat-${match.index}`} className="font-semibold text-amber-300 bg-amber-600/10 px-2 py-1 rounded">
            {match[4]}
          </span>
        )
      }

      lastIndex = regex.lastIndex
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex))
    }

    return parts.length > 0 ? parts : text
  }

  return (
    <div className="prose prose-invert max-w-none text-foreground">
      {parseContent(content)}
    </div>
  )
}
