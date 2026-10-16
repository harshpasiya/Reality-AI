"use client";

import { useState } from "react";
import Image from "next/image";
import { Home } from "lucide-react";

interface PropertyImageProps {
  src?: string | null;
  alt: string;
  className: string;
  sizes: string;
  priority?: boolean;
}

export default function PropertyImage({
  src,
  alt,
  className,
  sizes,
  priority = false,
}: PropertyImageProps) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const imageSrc = src?.trim();

  return (
    <div
      className={`relative overflow-hidden bg-zinc-100 dark:bg-zinc-800 ${className}`}
    >
      {imageSrc && failedSrc !== imageSrc ? (
        <Image
          src={imageSrc}
          alt={alt}
          fill
          unoptimized
          sizes={sizes}
          priority={priority}
          className="object-cover"
          onError={() => setFailedSrc(imageSrc)}
        />
      ) : (
        <div
          role="img"
          aria-label={`${alt} unavailable`}
          className="flex h-full w-full items-center justify-center text-zinc-400 dark:text-zinc-500"
        >
          <Home className="h-10 w-10" aria-hidden="true" />
        </div>
      )}
    </div>
  );
}
