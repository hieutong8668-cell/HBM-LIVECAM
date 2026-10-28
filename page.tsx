import { ShopeeHeader } from "@/components/shopee-header"
import { ServiceIcons } from "@/components/service-icons"
import { PromoBanner } from "@/components/promo-banner"
import { CategoryGrid } from "@/components/category-grid"
import { FlashSale } from "@/components/flash-sale"
import { ShopeeMall } from "@/components/shopee-mall"
import { TopSearch } from "@/components/top-search"

export default function HomePage() {
  return (
    <main className="min-h-screen bg-[#f5f5f5]">
      <ShopeeHeader />
      <ServiceIcons />
      <PromoBanner />
      <CategoryGrid />
      <FlashSale />
      <ShopeeMall />
      <TopSearch />
    </main>
  )
}
