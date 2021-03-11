import React, { useState } from 'react';
import { CheckboxInput } from "../../forms/inputs";
import { Loader } from '../loader';


const displayZaaktype = (zaaktype) => {
    return (
        <span className="zaak-record__zaaktype" title={`versie ${zaaktype.versiedatum}`}>
            {zaaktype.omschrijving}
        </span>
    );
}


function ZakenTable({ zaken, isLoaded, error, checkboxes, setCheckboxes }) {
    const [selectAll, setSelectAll] = useState(false);

    if (error) {
        return <div>Error in fetching zaken: {error.message}</div>;
    }

    if (!isLoaded) {
        return <Loader />;
    }

    return (
        <table className="table">
            <thead>
                <tr>
                    <th className="table__header">
                        <CheckboxInput
                          checked={selectAll}
                          name="selectAll"
                          onChange={(e) => {
                              const tick = !selectAll;
                              setSelectAll(tick);
                              const selectedCheckboxes = {
                                  ...Object.keys(checkboxes).reduce(
                                      (result, key) => ({...result, [key]: tick}),
                                      {}
                                  )
                              };
                              setCheckboxes(selectedCheckboxes);
                          }}
                      /></th>
                    <th className="table__header">Identificatie</th>
                    <th className="table__header">Zaaktype</th>
                    <th className="table__header" title="Zaak omschrijving">Omschrijving</th>
                    <th className="table__header">Looptijd</th>
                    <th className="table__header" title="Verantwoordelijke organisatie">VO</th>
                    <th className="table__header">Resultaattype</th>
                    <th className="table__header" title="Archiefactietermijn">Bewaartermijn</th>
                    <th className="table__header" title="Vernietigings-categorie selectielijst">VCS</th>
                    <th className="table__header" title="Relaties met andere zaken?">Relaties?</th>
                </tr>
            </thead>
            <tbody>
                {zaken.map(zaak => (
                <tr
                  key={zaak.url}
                  className={"zaak-record" + (!zaak.available ? " zaak-record--disabled" : "")}
                >
                    <td>
                      <CheckboxInput
                          checked={checkboxes[zaak.url] || false}
                          name={zaak.url}
                          onChange={(e) => {
                              const isChecked = !checkboxes[zaak.url];
                              setCheckboxes({...checkboxes, [zaak.url]: isChecked});
                              if (!isChecked) {
                                  setSelectAll(false);
                              }
                          }}
                          disabled={!zaak.available}
                      />
                    </td>
                    <td>{ zaak.identificatie }</td>
                    <td>{displayZaaktype(zaak.zaaktype)}</td>
                    <td>{zaak.omschrijving}</td>
                    <td>{ zaak.looptijd }</td>
                    <td>{ zaak.verantwoordelijkeOrganisatie }</td>
                    <td>{ zaak.resultaat ? zaak.resultaat.resultaattype.omschrijving : '-' }</td>
                    <td>{ zaak.resultaat ? zaak.resultaat.resultaattype.archiefactietermijn : '-'}</td>
                    <td>{ zaak.zaaktype.selectielijstProcestype ? zaak.zaaktype.selectielijstProcestype.nummer : "-" }</td>
                    <td>{ zaak.relevanteAndereZaken.length > 0 ? "Ja" : "Nee" }</td>
                </tr>
                ))}

            </tbody>
        </table>
    );
}

export { ZakenTable };
