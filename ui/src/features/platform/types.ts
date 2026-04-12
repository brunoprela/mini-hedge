import type { FundInfo as BaseFundInfo } from "@mini-hedge/api-types";

/** Extended FundInfo with customer context — will be in api-types after next gen. */
export type FundInfo = BaseFundInfo & {
  customer_id?: string | null;
  customer_name?: string | null;
};
