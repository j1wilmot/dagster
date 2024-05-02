import {gql} from '@apollo/client';

import {TABLE_SCHEMA_FRAGMENT} from './TableSchemaFragment';

export const METADATA_ENTRY_FRAGMENT = gql`
  fragment MetadataEntryFragment on MetadataEntry {
    label
    description
    ... on PathMetadataEntry {
      path
    }
    ... on NotebookMetadataEntry {
      path
    }
    ... on JsonMetadataEntry {
      jsonString
    }
    ... on UrlMetadataEntry {
      url
    }
    ... on TextMetadataEntry {
      text
    }
    ... on MarkdownMetadataEntry {
      mdStr
    }
    ... on PythonArtifactMetadataEntry {
      module
      name
    }
    ... on FloatMetadataEntry {
      floatValue
    }
    ... on TimestampMetadataEntry {
      timestamp
    }
    ... on IntMetadataEntry {
      intValue
      intRepr
    }
    ... on BoolMetadataEntry {
      boolValue
    }
    ... on PipelineRunMetadataEntry {
      runId
    }
    ... on AssetMetadataEntry {
      assetKey {
        path
      }
    }
    ... on JobMetadataEntry {
      jobName
      repositoryName
      locationName
    }
    ... on TableColumnLineageMetadataEntry {
      lineage {
        columnName
        columnDeps {
          assetKey {
            path
          }
          columnName
        }
      }
    }
    ... on TableMetadataEntry {
      table {
        records
        schema {
          ...TableSchemaFragment
        }
      }
    }
    ... on TableSchemaMetadataEntry {
      ...TableSchemaForMetadataEntry
    }
    ... on SouceCodeLocationsMetadataEntry {
      sources {
        key
        source {
          __typename
          ... on LocalFileSource {
            filePath
            lineNumber
          }
        }
      }
    }
  }

  fragment TableSchemaForMetadataEntry on TableSchemaMetadataEntry {
    schema {
      ...TableSchemaFragment
    }
  }

  ${TABLE_SCHEMA_FRAGMENT}
`;
