import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

/**
 * Renders a structured JSON table as an HTML table using shadcn UI components.
 * 
 * Used to display AI-extracted data tables from meeting minutes.
 */
export default function DataTable({ data }) {
  if (!data || data.length === 0) return null;
  
  const headers = data[0];
  const rows = data.slice(1, 6);

  return (
    <div className="mt-4 rounded-md border bg-muted/20">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {headers.map((cell, i) => (
              <TableHead key={i} className="h-8 text-[10px] font-bold uppercase tracking-tight text-muted-foreground">
                {cell}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow key={i} className="hover:bg-muted/40 transition-colors">
              {row.map((cell, j) => (
                <TableCell key={j} className="py-2 text-[11px] text-foreground/80">
                  {cell}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {data.length > 6 && (
        <div className="px-4 py-1 text-center text-[9px] text-muted-foreground italic border-t">
          Showing 5 of {data.length} rows
        </div>
      )}
    </div>
  );
}
