import ImageUpload from "@/components/ImageUpload";

export default function ImageUploadPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-start bg-zinc-50 p-6 text-zinc-900 md:p-12 dark:bg-black dark:text-zinc-100">
      <div className="mb-8 w-full max-w-2xl text-center sm:text-left">
        <h1 className="text-2xl font-bold tracking-tight">Image Upload</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Upload images with drag and drop preview.
        </p>
      </div>

      <ImageUpload />
    </main>
  );
}
