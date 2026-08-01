"use client"

import React from "react"
import { cn } from "@/lib/utils"

interface RichTextResponseProps {
  content: string
  /** "amber" (default) matches the original dark Reel Bot theme.
   *  "mono" matches the monochrome Stitch-designed dashboard - same
   *  parser, just black/grey accents instead of amber on a light surface. */
  theme?: "amber" | "mono"
}

const THEME_CLASSES = {
  amber: {
    h1: "text-xl font-bold text-amber-200 mt-4 mb-2",
    h2: "text-lg font-bold text-amber-300 mt-4 mb-2",
    h3: "text-base font-bold text-amber-400 mt-4 mb-2",
    code: "bg-black/50 border border-amber-600/20 rounded-lg p-4 my-3 overflow-x-auto text-xs font-mono text-amber-100",
    quote: "border-l-4 border-amber-600/50 pl-4 py-2 my-2 italic text-foreground/70",
    tableWrap: "my-3 overflow-x-auto rounded-lg border border-amber-600/20",
    thead: "bg-amber-600/10",
    th: "px-3 py-2 text-left font-semibold text-amber-300 border-b border-amber-600/20 whitespace-nowrap",
    tr: "border-b border-border/20 last:border-0",
    td: "px-3 py-2 whitespace-nowrap",
    p: "text-base leading-relaxed mb-2",
    bullet: "text-amber-400 flex-shrink-0",
    number: "text-amber-400 flex-shrink-0 font-semibold",
    listItem: "text-base",
    link: "font-semibold text-amber-300 underline decoration-amber-500/50 hover:text-amber-200 hover:decoration-amber-400",
    bold: "font-bold text-amber-300",
    italic: "italic text-foreground/80",
    inlineCode: "bg-black/30 px-2 py-1 rounded text-amber-100 text-xs font-mono",
    stat: "font-semibold text-amber-300 bg-amber-600/10 px-2 py-1 rounded",
    wrap: "prose prose-invert max-w-none text-foreground",
  },
  mono: {
    h1: "text-xl font-bold text-[#1a1c1c] mt-4 mb-2",
    h2: "text-lg font-bold text-[#1a1c1c] mt-4 mb-2",
    h3: "text-base font-bold text-[#1a1c1c] mt-4 mb-2",
    code: "bg-[#f3f3f4] border border-[#e2e2e2] rounded-lg p-4 my-3 overflow-x-auto text-xs font-mono text-[#1a1c1c]",
    quote: "border-l-4 border-[#cfc4c5] pl-4 py-2 my-2 italic text-[#4c4546]",
    tableWrap: "my-3 overflow-x-auto rounded-lg border border-[#e2e2e2]",
    thead: "bg-[#f3f3f4]",
    th: "px-3 py-2 text-left font-semibold text-[#1a1c1c] border-b border-[#e2e2e2] whitespace-nowrap",
    tr: "border-b border-[#e2e2e2] last:border-0",
    td: "px-3 py-2 whitespace-nowrap",
    p: "text-base leading-relaxed mb-2",
    bullet: "text-[#4c4546] flex-shrink-0",
    number: "text-[#1a1c1c] flex-shrink-0 font-semibold",
    listItem: "text-base",
    link: "font-semibold text-[#1a1c1c] underline decoration-[#7e7576] hover:decoration-[#1a1c1c]",
    bold: "font-bold text-[#1a1c1c]",
    italic: "italic text-[#4c4546]",
    inlineCode: "bg-[#eeeeee] px-2 py-1 rounded text-[#1a1c1c] text-xs font-mono",
    stat: "font-semibold text-[#1a1c1c] bg-[#eeeeee] px-2 py-1 rounded",
    wrap: "prose max-w-none text-[#1a1c1c]",
  },
} as const

export function RichTextResponse({ content, theme = "amber" }: RichTextResponseProps) {
  const T = THEME_CLASSES[theme]

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
          <h3 key={`h3-${i}`} className={T.h3}>
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
          <h2 key={`h2-${i}`} className={T.h2}>
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
          <h1 key={`h1-${i}`} className={T.h1}>
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
          <pre key={`code-${i}`} className={T.code}>
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
          <blockquote key={`quote-${i}`} className={T.quote}>
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
          <div key={`table-${i}`} className={T.tableWrap}>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className={T.thead}>
                  {header.map((cell, idx) => (
                    <th key={idx} className={T.th}>
                      {renderInlineFormatting(cell)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bodyRows.map((row, rIdx) => (
                  <tr key={rIdx} className={T.tr}>
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className={T.td}>
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
          <p key={`p-${i}`} className={T.p}>
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
              <span className={T.bullet}>•</span>
              <span className={T.listItem}>{renderInlineFormatting(item)}</span>
            </li>
          ))}
        </ul>
      )
    }

    return (
      <ol key={`list-${Math.random()}`} className="space-y-2 my-3 ml-4">
        {items.map((item, idx) => (
          <li key={idx} className="flex gap-2">
            <span className={T.number}>{idx + 1}.</span>
            <span className={T.listItem}>{renderInlineFormatting(item)}</span>
          </li>
        ))}
      </ol>
    )
  }

  const renderInlineFormatting = (text: string) => {
    // The LLM sometimes emits literal "<br>" inside table cells to force a
    // line break within one cell - without this split, it rendered as the
    // raw string "<br>" instead of an actual line break.
    const brSegments = text.split(/<br\s*\/?>/i)
    if (brSegments.length > 1) {
      const withBreaks: React.ReactNode[] = []
      brSegments.forEach((segment, idx) => {
        if (idx > 0) withBreaks.push(<br key={`br-${idx}`} />)
        withBreaks.push(...formatInlineSegment(segment))
      })
      return withBreaks
    }
    return formatInlineSegment(text)
  }

  const formatInlineSegment = (text: string) => {
    const parts: React.ReactNode[] = []
    let lastIndex = 0

    // Pattern for [link](url), **bold**, *italic*, `code`, and bare numbers.
    // Link goes first: an LLM-provided [desc](url) must win over any other
    // rule that might otherwise match inside its bracket/paren text.
    const pattern = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|(\d+(?:,\d+)*%?|\d+(?:,\d+)* (?:views?|likes?|comments?|shares?|reels?|reel))/gi

    let match
    const regex = new RegExp(pattern)

    while ((match = regex.exec(text)) !== null) {
      // Add text before match
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index))
      }

      if (match[1] && match[2]) {
        // Markdown link -> a real, clickable anchor to the reel's actual
        // Instagram permalink, opened in a new tab.
        parts.push(
          <a
            key={`link-${match.index}`}
            href={match[2]}
            target="_blank"
            rel="noopener noreferrer"
            className={T.link}
          >
            {match[1]}
          </a>
        )
      } else if (match[3]) {
        // Bold - re-parsed recursively: the LLM sometimes writes
        // **[link](url)** (bolding its own link). Since "**" starts before
        // "[" in the string, this pattern matches bold first and swallows
        // the whole link as plain text unless the bold content is itself
        // re-run through the same parser.
        parts.push(
          <strong key={`bold-${match.index}`} className={T.bold}>
            {formatInlineSegment(match[3])}
          </strong>
        )
      } else if (match[4]) {
        // Italic - same recursive re-parse, for the same reason.
        parts.push(
          <em key={`italic-${match.index}`} className={T.italic}>
            {formatInlineSegment(match[4])}
          </em>
        )
      } else if (match[5]) {
        // Inline code
        parts.push(
          <code key={`code-${match.index}`} className={T.inlineCode}>
            {match[5]}
          </code>
        )
      } else if (match[6]) {
        // Numbers/stats
        parts.push(
          <span key={`stat-${match.index}`} className={T.stat}>
            {match[6]}
          </span>
        )
      }

      lastIndex = regex.lastIndex
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex))
    }

    // Always an array, never a bare string: renderInlineFormatting spreads
    // this result with "...formatInlineSegment(segment)" when handling
    // "<br>" splits - spreading a string would explode it into characters.
    return parts.length > 0 ? parts : [text]
  }

  return <div className={T.wrap}>{parseContent(content)}</div>
}
