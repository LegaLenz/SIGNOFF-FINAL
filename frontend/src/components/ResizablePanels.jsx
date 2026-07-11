import { Children } from 'react';
import { Group, Panel, Separator } from 'react-resizable-panels';

/**
 * Wraps the two-pane analysis layout (docs/design_spec.md): document panel
 * default 65% / min 40%, chat panel default 35% / min 25%, drag-resizable.
 * Takes exactly two children — [0] renders in the document panel, [1] in
 * the chat panel — so callers just pass their own panel components in.
 */
export default function ResizablePanels({ children }) {
  const [documentPanel, chatPanel] = Children.toArray(children);

  return (
    <Group orientation="horizontal" className="flex h-full min-h-0 w-full">
      <Panel id="doc-panel" defaultSize="65%" minSize="40%" maxSize="75%" className="min-w-0 overflow-y-auto bg-surface">
        {documentPanel}
      </Panel>

      <Separator
        id="resize-handle"
        className="group relative flex w-1.5 shrink-0 cursor-col-resize items-stretch bg-transparent outline-none"
      >
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 bg-border transition-colors duration-150 group-data-[separator=hover]:bg-border-strong group-data-[separator=active]:bg-border-strong group-data-[separator=focus]:bg-border-strong"
        />
      </Separator>

      <Panel id="chat-panel" defaultSize="35%" minSize="25%" maxSize="60%" className="min-w-[260px] bg-background">
        {chatPanel}
      </Panel>
    </Group>
  );
}
