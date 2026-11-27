import React, { useMemo } from 'react';
import {
  ClientSideRowModelModule,
  CellStyleModule,
  ColumnAutoSizeModule,
  CustomFilterModule,
  DateFilterModule,
  LocaleModule,
  ModuleRegistry,
  NumberFilterModule,
  PaginationModule,
  RowAutoHeightModule,
  TextFilterModule,
  themeQuartz,
  colorSchemeDarkBlue,
  colorSchemeLight,
} from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import { useTheme } from '../../context/ThemeContext';
import { deriveAccentTokens } from '../../utils/colorUtils';

ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  CellStyleModule,
  ColumnAutoSizeModule,
  CustomFilterModule,
  DateFilterModule,
  LocaleModule,
  NumberFilterModule,
  PaginationModule,
  RowAutoHeightModule,
  TextFilterModule,
]);

const sharedThemeParams = {
  wrapperBorder: false,
  wrapperBorderRadius: 0,
  autoHeightMinBodyHeight: 160,
  cellHorizontalPaddingScale: 1.1,
  rowVerticalPaddingScale: 1.15,
  fontSize: 13.5,
  headerFontSize: 11.5,
  headerFontWeight: 600,
};

const lightBaseParams = {
  ...sharedThemeParams,
  backgroundColor: 'transparent',
  chromeBackgroundColor: 'rgba(248, 250, 252, 0.65)',
  foregroundColor: '#0f172a',
  borderColor: 'rgba(15, 23, 42, 0.08)',
  oddRowBackgroundColor: 'rgba(248, 250, 252, 0.35)',
};

const darkBaseParams = {
  ...sharedThemeParams,
  backgroundColor: 'transparent',
  chromeBackgroundColor: 'rgba(255, 255, 255, 0.035)',
  foregroundColor: '#f4f7ff',
  borderColor: 'rgba(255, 255, 255, 0.085)',
  oddRowBackgroundColor: 'rgba(255, 255, 255, 0.015)',
};

/**
 * Shared AG Grid wrapper synchronized with SenderX light/dark theme and responsive layout.
 */
export default function DataGrid({
  rowData = [],
  columnDefs = [],
  loading = false,
  emptyMessage = 'No records found.',
  getRowId,
  pagination = false,
  paginationPageSize = 20,
  rowHeight = 52,
  defaultColDef: customDefaultColDef,
  gridOptions,
}) {
  const { isDark, preferences } = useTheme();
  const gridTheme = useMemo(() => {
    const accent = deriveAccentTokens(preferences?.accentColor);
    const scheme = isDark ? colorSchemeDarkBlue : colorSchemeLight;
    const base = isDark ? darkBaseParams : lightBaseParams;
    return themeQuartz.withPart(scheme).withParams({
      ...base,
      accentColor: accent.color,
      selectedRowBackgroundColor: accent.subtle,
    });
  }, [isDark, preferences?.accentColor]);

  const defaultColDef = useMemo(
    () => ({
      sortable: true,
      filter: true,
      resizable: true,
      flex: 1,
      minWidth: 110,
      ...customDefaultColDef,
    }),
    [customDefaultColDef]
  );

  const normalizedColumnDefs = useMemo(
    () =>
      columnDefs.map((col) =>
        col.cellClass === 'ag-actions-cell'
          ? { flex: 0, width: col.width ?? col.minWidth, ...col }
          : col
      ),
    [columnDefs]
  );

  const localeText = useMemo(
    () => ({
      noRowsToShow: emptyMessage,
    }),
    [emptyMessage]
  );

  return (
    <div className="senderx-ag-grid" style={{ width: '100%' }}>
      <AgGridReact
        theme={gridTheme}
        rowData={Array.isArray(rowData) ? rowData : []}
        columnDefs={normalizedColumnDefs}
        defaultColDef={defaultColDef}
        loading={loading}
        domLayout="autoHeight"
        getRowId={getRowId}
        pagination={pagination}
        paginationPageSize={paginationPageSize}
        paginationPageSizeSelector={[10, 20, 50]}
        rowHeight={rowHeight}
        suppressCellFocus
        animateRows
        localeText={localeText}
        {...gridOptions}
      />
    </div>
  );
}
