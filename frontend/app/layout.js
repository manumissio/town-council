import "./globals.css";

export const metadata = {
  title: "Town Council Search",
  description: "Search local government meeting minutes.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">{children}</body>
    </html>
  );
}
