import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from '../../../components/ui/button'

describe('Button Component', () => {
  describe('rendering', () => {
    it('should render button with text', () => {
      render(<Button>Click me</Button>)

      expect(screen.getByRole('button')).toBeInTheDocument()
      expect(screen.getByText('Click me')).toBeInTheDocument()
    })

    it('should render as button by default', () => {
      render(<Button>Test</Button>)

      const button = screen.getByRole('button')
      expect(button.tagName).toBe('BUTTON')
    })

    it('should support custom className', () => {
      render(<Button className="custom-class">Test</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('custom-class')
    })
  })

  describe('variants', () => {
    it('should apply default variant styles', () => {
      render(<Button>Default</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('bg-primary')
    })

    it('should apply destructive variant styles', () => {
      render(<Button variant="destructive">Delete</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('bg-destructive')
    })

    it('should apply outline variant styles', () => {
      render(<Button variant="outline">Outline</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('border-input')
    })

    it('should apply secondary variant styles', () => {
      render(<Button variant="secondary">Secondary</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('bg-secondary')
    })

    it('should apply ghost variant styles', () => {
      render(<Button variant="ghost">Ghost</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('hover:bg-accent')
    })

    it('should apply link variant styles', () => {
      render(<Button variant="link">Link</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('text-primary')
    })
  })

  describe('sizes', () => {
    it('should apply default size styles', () => {
      render(<Button>Default Size</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('h-10', 'px-4', 'py-2')
    })

    it('should apply small size styles', () => {
      render(<Button size="sm">Small</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('h-9', 'px-3')
    })

    it('should apply large size styles', () => {
      render(<Button size="lg">Large</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('h-11', 'px-8')
    })

    it('should apply icon size styles', () => {
      render(<Button size="icon">🔍</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('h-10', 'w-10')
    })
  })

  describe('states', () => {
    it('should be disabled when disabled prop is true', () => {
      render(<Button disabled>Disabled</Button>)

      const button = screen.getByRole('button')
      expect(button).toBeDisabled()
      expect(button).toHaveClass('disabled:pointer-events-none', 'disabled:opacity-50')
    })

    it('should not trigger onClick when disabled', async () => {
      const user = userEvent.setup()
      const handleClick = vi.fn()

      render(
        <Button disabled onClick={handleClick}>
          Disabled
        </Button>
      )

      const button = screen.getByRole('button')
      await user.click(button)

      expect(handleClick).not.toHaveBeenCalled()
    })

    it('should support loading state', () => {
      render(<Button disabled>Loading...</Button>)

      const button = screen.getByRole('button')
      expect(button).toBeDisabled()
    })
  })

  describe('interactions', () => {
    it('should call onClick when clicked', async () => {
      const user = userEvent.setup()
      const handleClick = vi.fn()

      render(<Button onClick={handleClick}>Click me</Button>)

      const button = screen.getByRole('button')
      await user.click(button)

      expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('should handle keyboard interactions', () => {
      const handleClick = vi.fn()

      render(<Button onClick={handleClick}>Press me</Button>)

      const button = screen.getByRole('button')
      fireEvent.keyDown(button, { key: 'Enter', code: 'Enter' })

      expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('should support focus and blur', () => {
      render(<Button>Focusable</Button>)

      const button = screen.getByRole('button')
      button.focus()

      expect(button).toHaveFocus()

      button.blur()
      expect(button).not.toHaveFocus()
    })
  })

  describe('accessibility', () => {
    it('should have correct role', () => {
      render(<Button>Accessible</Button>)

      expect(screen.getByRole('button')).toBeInTheDocument()
    })

    it('should support aria-label', () => {
      render(<Button aria-label="Close dialog">×</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('aria-label', 'Close dialog')
    })

    it('should support aria-describedby', () => {
      render(
        <div>
          <Button aria-describedby="help-text">Submit</Button>
          <div id="help-text">This will submit the form</div>
        </div>
      )

      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('aria-describedby', 'help-text')
    })

    it('should be keyboard navigable', () => {
      render(<Button>Keyboard accessible</Button>)

      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('tabIndex', '0')
    })
  })

  describe('as prop', () => {
    it('should render as different element when asChild is used', () => {
      render(
        <Button asChild>
          <a href="/test">Link Button</a>
        </Button>
      )

      const link = screen.getByRole('link')
      expect(link).toBeInTheDocument()
      expect(link).toHaveAttribute('href', '/test')
    })
  })

  describe('custom props', () => {
    it('should pass through HTML button props', () => {
      render(
        <Button
          type="submit"
          form="test-form"
          name="submit-button"
          value="submit"
        >
          Submit
        </Button>
      )

      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('type', 'submit')
      expect(button).toHaveAttribute('form', 'test-form')
      expect(button).toHaveAttribute('name', 'submit-button')
      expect(button).toHaveAttribute('value', 'submit')
    })

    it('should support data attributes', () => {
      render(
        <Button data-testid="custom-button" data-analytics="click">
          Test
        </Button>
      )

      const button = screen.getByTestId('custom-button')
      expect(button).toHaveAttribute('data-analytics', 'click')
    })
  })

  describe('combination of props', () => {
    it('should handle multiple variants and sizes together', () => {
      render(
        <Button variant="outline" size="lg" className="custom-class">
          Outline Large
        </Button>
      )

      const button = screen.getByRole('button')
      expect(button).toHaveClass('border-input') // outline variant
      expect(button).toHaveClass('h-11', 'px-8') // large size
      expect(button).toHaveClass('custom-class') // custom className
    })

    it('should handle disabled state with variants', () => {
      render(
        <Button variant="destructive" disabled>
          Disabled Destructive
        </Button>
      )

      const button = screen.getByRole('button')
      expect(button).toBeDisabled()
      expect(button).toHaveClass('bg-destructive')
      expect(button).toHaveClass('disabled:opacity-50')
    })
  })

  describe('edge cases', () => {
    it('should handle empty children', () => {
      render(<Button></Button>)

      const button = screen.getByRole('button')
      expect(button).toBeInTheDocument()
      expect(button.textContent).toBe('')
    })

    it('should handle complex children', () => {
      render(
        <Button>
          <span>Icon</span>
          <span>Text</span>
        </Button>
      )

      const button = screen.getByRole('button')
      expect(button).toHaveTextContent('IconText')
      expect(button.children).toHaveLength(2)
    })

    it('should maintain button behavior with complex styling', () => {
      const handleClick = vi.fn()

      render(
        <Button
          onClick={handleClick}
          variant="ghost"
          size="sm"
          className="rounded-full border-2"
        >
          Complex Button
        </Button>
      )

      const button = screen.getByRole('button')
      fireEvent.click(button)

      expect(handleClick).toHaveBeenCalled()
      expect(button).toHaveClass('hover:bg-accent', 'h-9', 'px-3', 'rounded-full', 'border-2')
    })
  })
})