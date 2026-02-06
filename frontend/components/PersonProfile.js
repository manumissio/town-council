import { useState, useEffect } from "react";
import { X, User, Loader2, Building2, Info } from "lucide-react";

/**
 * PersonProfile Component
 * 
 * RESTORED: This version brings back the original 'Sleek' modal design.
 * It uses a bold blue header, deep rounded corners, and a clean backdrop blur.
 */
export default function PersonProfile({ personId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!personId) return;
    
    const fetchPerson = async () => {
      setLoading(true);
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiUrl}/person/${personId}`);
        const json = await res.json();
        setData(json);
      } catch (err) {
        console.error("Failed to fetch person", err);
      } finally {
        setLoading(false);
      }
    };

    fetchPerson();
  }, [personId]);

  if (!personId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white w-full max-w-2xl rounded-[2.5rem] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        {/* Header Section */}
        <div className="bg-blue-600 p-8 text-white relative">
          <button 
            onClick={onClose}
            className="absolute top-6 right-6 p-2 hover:bg-white/10 rounded-full transition-colors"
            title="Close Profile"
          >
            <X className="w-6 h-6" />
          </button>
          
          <div className="flex items-center gap-6">
            <div className="bg-white/20 p-4 rounded-3xl backdrop-blur-md">
              <User className="w-12 h-12 text-white" />
            </div>
            <div>
              <h2 className="text-3xl font-bold tracking-tight">{loading ? "Loading..." : data?.name}</h2>
              <p className="text-blue-100 font-medium mt-1">{data?.current_role || "Public Official"}</p>
            </div>
          </div>
        </div>

        {/* Details Section */}
        <div className="p-10 max-h-[60vh] overflow-y-auto">
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center gap-4 text-gray-400">
              <Loader2 className="w-10 h-10 animate-spin" />
              <p className="font-bold text-xs uppercase tracking-widest">Retrieving History...</p>
            </div>
          ) : (
            <div className="space-y-8">
              {/* Committee History */}
              <div className="space-y-4">
                <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Legislative History</h3>
                <div className="grid gap-3">
                  {data?.roles?.map((role, i) => (
                    <div key={i} className="flex items-center justify-between p-5 bg-gray-50 rounded-2xl border border-gray-100 group hover:border-blue-200 hover:bg-blue-50 transition-all">
                      <div className="flex items-center gap-4">
                        <div className="bg-white p-2.5 rounded-xl shadow-sm group-hover:text-blue-600 transition-colors">
                          <Building2 className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="font-bold text-gray-900 group-hover:text-blue-900">{role.body}</p>
                          <p className="text-xs text-gray-500 font-medium">{role.city}</p>
                        </div>
                      </div>
                      <span className="px-3 py-1 bg-white border border-gray-200 text-[10px] font-bold text-gray-500 rounded-lg uppercase tracking-tight shadow-sm group-hover:border-blue-100 group-hover:text-blue-600 transition-all">
                        {role.role}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Accountability Note */}
              <div className="pt-6 border-t border-gray-100">
                <div className="flex items-start gap-3 p-4 bg-gray-50 rounded-2xl">
                  <Info className="w-4 h-4 text-gray-400 mt-0.5" />
                  <p className="text-xs text-gray-500 leading-relaxed italic">
                    Note: Memberships and roles are extracted automatically from official meeting minutes using AI logic based on the Open Civic Data standard.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
