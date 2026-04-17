/**
 * Shared form library exports.
 *
 * Thin re-export layer so feature code doesn't couple directly to
 * `react-hook-form` / `zod` / `@hookform/resolvers` import paths. Lets us
 * swap dependencies later without ripping through every form.
 */

export { Controller, FormProvider, useForm, useFormContext } from "react-hook-form";
export { zodResolver } from "@hookform/resolvers/zod";
export { z } from "zod";
