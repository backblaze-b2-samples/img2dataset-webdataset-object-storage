"use client";

import { type ReactNode, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useCreateCorpus, useFiles, useUpdateCorpus } from "@/lib/queries";
import {
  OUTPUT_FORMAT_LABELS,
  RESIZE_MODE_LABELS,
  outputFormatLabel,
  resizeModeLabel,
} from "@/lib/corpus-labels";
import { UPLOAD_PREFIX, isUrlListFile } from "@/lib/url-list-files";
import type { Corpus } from "@img2dataset-webdataset-object-storage/shared";

const schema = z
  .object({
    name: z.string().min(2, "2–50 characters").max(50),
    description: z.string().max(160, "160 characters max").optional(),
    url_list_source: z.enum(["seed", "uploaded"]),
    bucket_key: z.string().optional(),
    output_format: z.enum(["webdataset", "parquet", "files"]),
    resize_mode: z.enum(["border", "keep_ratio", "center_crop", "no"]),
    image_size: z.enum(["256", "384", "512"]),
  })
  .refine((v) => v.url_list_source !== "uploaded" || !!v.bucket_key, {
    message: "Pick an uploaded URL-list file",
    path: ["bucket_key"],
  });

type CorpusFormValues = z.infer<typeof schema>;

function toDefaults(corpus?: Corpus): CorpusFormValues {
  return {
    name: corpus?.name ?? "",
    description: corpus?.description ?? "",
    url_list_source: corpus?.url_list_source ?? "seed",
    bucket_key: corpus?.bucket_key ?? undefined,
    output_format: corpus?.output_format ?? "webdataset",
    resize_mode: corpus?.resize_mode ?? "border",
    image_size: String(corpus?.image_size ?? 256) as "256" | "384" | "512",
  };
}

export function CorpusFormDialog({
  mode,
  corpus,
  trigger,
}: {
  mode: "create" | "edit";
  corpus?: Corpus;
  trigger: ReactNode;
}) {
  const isEdit = mode === "edit";
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const createCorpus = useCreateCorpus();
  const updateCorpus = useUpdateCorpus(corpus?.id ?? "");
  // Listed straight from the upload prefix, so the app's own ingest output
  // (img2dataset/<id>/shards/*.parquet) never reaches the picker.
  const { data: files = [] } = useFiles(UPLOAD_PREFIX, 1000, {
    enabled: open && !isEdit,
  });

  const form = useForm<CorpusFormValues>({
    resolver: zodResolver(schema),
    defaultValues: toDefaults(corpus),
  });
  const source = useWatch({ control: form.control, name: "url_list_source" });
  const urlListFiles = files.filter((f) => isUrlListFile(f.key));
  const hasUrlListFiles = urlListFiles.length > 0;

  const onSubmit = async (values: CorpusFormValues) => {
    try {
      if (isEdit && corpus) {
        await updateCorpus.mutateAsync({
          name: values.name,
          description: values.description ?? "",
        });
        toast.success("Corpus updated");
        setOpen(false);
      } else {
        const created = await createCorpus.mutateAsync({
          name: values.name,
          description: values.description ?? "",
          url_list_source: values.url_list_source,
          bucket_key:
            values.url_list_source === "uploaded" ? values.bucket_key : null,
          output_format: values.output_format,
          resize_mode: values.resize_mode,
          image_size: Number(values.image_size) as 256 | 384 | 512,
        });
        toast.success("Corpus created", {
          description: "Ingest started — streaming shards to B2.",
        });
        setOpen(false);
        router.push(`/corpora/${created.id}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save the corpus");
    }
  };

  const submitting = createCorpus.isPending || updateCorpus.isPending;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit corpus" : "New corpus"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Rename or re-describe this corpus. Ingest parameters are fixed at creation and shown read-only."
              : "Configure an img2dataset ingest. Shards stream straight to B2 under img2dataset/<id>/."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. Nature thumbnails 256px" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea
                      className="resize-none"
                      placeholder="Optional — what this training corpus is for"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {isEdit && corpus ? (
              <ReadOnlyParams corpus={corpus} />
            ) : (
              <>
                <FormField
                  control={form.control}
                  name="url_list_source"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>URL list</FormLabel>
                      <FormControl>
                        <RadioGroup
                          onValueChange={field.onChange}
                          value={field.value}
                          className="flex flex-wrap gap-4"
                        >
                          <label className="flex items-center gap-2 text-sm cursor-pointer">
                            <RadioGroupItem value="seed" /> Built-in seed list
                          </label>
                          <label className="flex items-center gap-2 text-sm cursor-pointer">
                            <RadioGroupItem value="uploaded" /> Uploaded file
                          </label>
                        </RadioGroup>
                      </FormControl>
                      <FormDescription>
                        Defaults to the built-in 24-image sample list — a sound
                        test run with no external data or extra API key.
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {source === "uploaded" && (
                  <FormField
                    control={form.control}
                    name="bucket_key"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Uploaded URL-list file</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger disabled={!hasUrlListFiles}>
                              <SelectValue
                                placeholder={
                                  hasUrlListFiles
                                    ? "Select a .tsv / .csv / .parquet file"
                                    : "No uploaded URL lists yet"
                                }
                              />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {urlListFiles.map((f) => (
                              <SelectItem key={f.key} value={f.key}>
                                {f.key}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          {hasUrlListFiles
                            ? "Your uploads only — the app's own ingest output is not listed."
                            : "Upload a TSV/CSV/parquet with url and caption columns on the Upload page first."}
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}

                <FormField
                  control={form.control}
                  name="output_format"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Output format</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {Object.entries(OUTPUT_FORMAT_LABELS).map(
                            ([value, { label }]) => (
                              <SelectItem key={value} value={value}>
                                {label}
                              </SelectItem>
                            ),
                          )}
                        </SelectContent>
                      </Select>
                      <FormDescription>
                        WebDataset (default) writes ready-to-train <code>.tar</code>{" "}
                        shards you can stream back.
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="resize_mode"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Resize mode</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {Object.entries(RESIZE_MODE_LABELS).map(
                            ([value, { label }]) => (
                              <SelectItem key={value} value={value}>
                                {label}
                              </SelectItem>
                            ),
                          )}
                        </SelectContent>
                      </Select>
                      <FormDescription>Default: border (pad to square).</FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="image_size"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Image size</FormLabel>
                      <FormControl>
                        <RadioGroup
                          onValueChange={field.onChange}
                          value={field.value}
                          className="flex gap-4"
                        >
                          {["256", "384", "512"].map((size) => (
                            <label
                              key={size}
                              className="flex items-center gap-2 text-sm cursor-pointer"
                            >
                              <RadioGroupItem value={size} /> {size}px
                            </label>
                          ))}
                        </RadioGroup>
                      </FormControl>
                      <FormDescription>Default: 256px (fast, small shards).</FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </>
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting
                  ? "Saving..."
                  : isEdit
                    ? "Save changes"
                    : "Create & ingest"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

/** Immutable ingest params, shown read-only on the edit form. */
function ReadOnlyParams({ corpus }: { corpus: Corpus }) {
  const rows: [string, string][] = [
    [
      "URL list",
      corpus.url_list_source === "seed"
        ? "Built-in seed list"
        : (corpus.bucket_key ?? "Uploaded file"),
    ],
    ["Output format", outputFormatLabel(corpus.output_format)],
    ["Resize mode", resizeModeLabel(corpus.resize_mode)],
    ["Image size", `${corpus.image_size}px`],
  ];
  return (
    <div className="rounded-md border border-border p-3">
      <p className="mb-2 text-xs font-medium text-muted-foreground">
        Ingest parameters (create-time immutable)
      </p>
      <dl className="space-y-1.5">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-3">
            <dt className="text-sm text-muted-foreground">{label}</dt>
            <dd className="truncate text-xs font-medium">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
