// Every customer by name, with call count and last contact — GET /customers.
import { getCustomers } from "@/lib/api";
import ApiNotice from "@/components/ApiNotice";
import CustomerTable from "@/components/CustomerTable";

export default async function CustomerList() {
  const { data: customers, error } = await getCustomers();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Customers</h1>
        <p className="mt-1 text-sm text-slate-500">
          Every caller in the dataset. Click a name for their full call history.
        </p>
      </div>

      {error && <ApiNotice error={error} />}
      {customers && <CustomerTable customers={customers} />}
    </div>
  );
}
