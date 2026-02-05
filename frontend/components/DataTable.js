/**
 * Renders a structured JSON table as an HTML table.
 * 
 * Used to display AI-extracted data tables from meeting minutes.
 */
export default function DataTable({ data }) {
  if (!data || data.length === 0) return null;
  
  const headers = data[0];
  const rows = data.slice(1, 6);

  return (
    <div className="mt-4 overflow-x-auto border border-gray-100 rounded-lg shadow-inner bg-gray-50/50">
      <table className="min-w-full divide-y divide-gray-200">
        <thead>
          <tr>
            {headers.map((cell, i) => (
              <th key={i} className="px-4 py-2 text-left text-[10px] font-bold text-gray-400 uppercase tracking-tight">
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-white/50 transition-colors">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2 whitespace-nowrap text-[11px] text-gray-600">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length > 6 && (
        <div className="px-4 py-1 text-center text-[9px] text-gray-400 italic border-t border-gray-100">
          Showing 5 of {data.length} rows
        </div>
      )}
    </div>
  );
}
