import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { FAQ } from "@/content/faq";

// FAQ section — renders content/faq.ts verbatim (the F7 chatbot consumes the
// same file; never fork the copy here).
export function Faq() {
  return (
    <section>
      <div className="mx-auto w-full max-w-2xl px-4 py-20 sm:px-6 lg:py-28">
        <div className="mb-10 text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Frequently asked questions
          </h2>
        </div>
        <Accordion type="single" collapsible className="w-full">
          {FAQ.map((entry, i) => (
            <AccordionItem key={entry.question} value={`item-${i}`}>
              <AccordionTrigger className="text-left">{entry.question}</AccordionTrigger>
              <AccordionContent className="text-muted-foreground">
                {entry.answer}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}
