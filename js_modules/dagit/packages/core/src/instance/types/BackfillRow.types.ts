// Generated GraphQL types, do not edit manually.

import * as Types from '../../graphql/types';

export type SingleBackfillCountsQueryVariables = Types.Exact<{
  backfillId: Types.Scalars['String'];
}>;

export type SingleBackfillCountsQuery = {
  __typename: 'DagitQuery';
  partitionBackfillOrError:
    | {__typename: 'BackfillNotFoundError'}
    | {
        __typename: 'PartitionBackfill';
        id: string;
        partitionStatusCounts: Array<{
          __typename: 'PartitionStatusCounts';
          runStatus: Types.RunStatus;
          count: number;
        }>;
      }
    | {__typename: 'PythonError'};
};

export type SingleBackfillQueryVariables = Types.Exact<{
  backfillId: Types.Scalars['String'];
}>;

export type SingleBackfillQuery = {
  __typename: 'DagitQuery';
  partitionBackfillOrError:
    | {__typename: 'BackfillNotFoundError'}
    | {
        __typename: 'PartitionBackfill';
        id: string;
        backfillRunStatuses:
          | {
              __typename: 'AssetBackfillRunStatuses';
              results: Array<{
                __typename: 'AssetBackfillRunStatus';
                runId: string | null;
                runStatus: Types.RunStatus | null;
                assetBackfillRunPartitionName: string | null;
              }>;
            }
          | {
              __typename: 'PartitionStatuses';
              results: Array<{
                __typename: 'PartitionStatus';
                id: string;
                runId: string | null;
                runStatus: Types.RunStatus | null;
                jobBackfillRunPartitionName: string;
              }>;
            };
      }
    | {__typename: 'PythonError'};
};

export type PartitionStatusesForBackfillFragment = {
  __typename: 'PartitionStatuses';
  results: Array<{
    __typename: 'PartitionStatus';
    id: string;
    runId: string | null;
    runStatus: Types.RunStatus | null;
    jobBackfillRunPartitionName: string;
  }>;
};

export type AssetBackfillRunStatusesFragment = {
  __typename: 'AssetBackfillRunStatuses';
  results: Array<{
    __typename: 'AssetBackfillRunStatus';
    runId: string | null;
    runStatus: Types.RunStatus | null;
    assetBackfillRunPartitionName: string | null;
  }>;
};
