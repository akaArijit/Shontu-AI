'use client';

import { forwardRef, TableHTMLAttributes, ThHTMLAttributes, TdHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

interface TableProps extends TableHTMLAttributes<HTMLTableElement> {
  stickyHeader?: boolean;
}

export const Table = forwardRef<HTMLTableElement, TableProps>(
  ({ className, stickyHeader, children, ...props }, ref) => (
    <div className="w-full overflow-x-auto">
      <table
        ref={ref}
        className={cn('w-full text-sm', stickyHeader && '[&_thead_tr_th]:sticky [&_thead_tr_th]:top-0 [&_thead_tr_th]:z-10', className)}
        {...props}
      >
        {children}
      </table>
    </div>
  )
);

Table.displayName = 'Table';

export const TableHeader = forwardRef<HTMLTableSectionElement, HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, children, ...props }, ref) => (
    <thead ref={ref} className={cn('[&_tr]:border-b', className)} {...props}>
      {children}
    </thead>
  )
);
TableHeader.displayName = 'TableHeader';

export const TableBody = forwardRef<HTMLTableSectionElement, HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, children, ...props }, ref) => (
    <tbody ref={ref} className={cn('[&_tr:last-child]:border-0', className)} {...props}>
      {children}
    </tbody>
  )
);
TableBody.displayName = 'TableBody';

export const TableRow = forwardRef<HTMLTableRowElement, HTMLAttributes<HTMLTableRowElement>>(
  ({ className, clickable, ...props }, ref) => (
    <tr
      ref={ref}
      className={cn(
        'border-b border-neutral-100 transition-colors',
        clickable && 'hover:bg-neutral-50 cursor-pointer',
        'data-[state=selected]:bg-primary-50',
        className
      )}
      {...props}
    />
  )
);
TableRow.displayName = 'TableRow';

export const TableHead = forwardRef<HTMLTableCellElement, ThHTMLAttributes<HTMLTableCellElement>>(
  ({ className, align = 'left', width, ...props }, ref) => (
    <th
      ref={ref}
      className={cn(
        'px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs',
        align === 'center' && 'text-center',
        align === 'right' && 'text-right',
        width && `w-[${width}]`,
        className
      )}
      style={{ width }}
      {...props}
    />
  )
);
TableHead.displayName = 'TableHead';

export const TableCell = forwardRef<HTMLTableCellElement, TdHTMLAttributes<HTMLTableCellElement>>(
  ({ className, align = 'left', ...props }, ref) => (
    <td
      ref={ref}
      className={cn('px-4 py-3 text-neutral-900', align === 'center' && 'text-center', align === 'right' && 'text-right', className)}
      {...props}
    />
  )
);
TableCell.displayName = 'TableCell';