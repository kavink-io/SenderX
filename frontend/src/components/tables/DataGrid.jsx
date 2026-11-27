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

const lightTheme = themeQuartz.withPart(colorSchemeLight).withParams({
  ...sharedThemeParams,
  backgroundColor: 'transparent',
  chromeBackgroundColor: 'rgba(248, 250, 252, 0.65)',
  foregroundColor: '#0f172a',
  borderColor: 'rgba(15, 23, 42, 0.08)',
  oddRowBackgroundColor: 'rgba(248, 250, 252, 0.35)',
  selectedRowBackgroundColor: 'rgba(37, 99, 235, 0.08)',
});

const darkTheme = themeQuartz.withPart(colorSchemeDarkBlue).withParams({
  ...sharedThemeParams,
  backgroundColor: 'transparent',
  chromeBackgroundColor: 'rgba(255, 255, 255, 0.035)',
  foregroundColor: '#f4f7ff',
  borderColor: 'rgba(255, 255, 255, 0.085)',
  oddRowBackgroundColor: 'rgba(255, 255, 255, 0.015)',
  selectedRowBackgroundColor: 'rgba(56, 217, 245, 0.10)',
});

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
  const { isDark } = useTheme();

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
        theme={isDark ? darkTheme : lightTheme}
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
